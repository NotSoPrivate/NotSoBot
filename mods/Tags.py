import asyncio
import random
import re
import traceback
from urllib.parse import quote

import discord
from discord.ext import commands

from mods.cog import Cog
from utils import checks
from utils.funcs import get_prefix, LimitError
from utils.paginator import CannotPaginate, Pages


class Tag_Error(Exception): pass
class Tag_Script_Error(Tag_Error): pass
class Tag_Find_Error(Tag_Error): pass

class Tag_NSFW(Tag_Error):
	def __init__(self):
		super().__init__(
			"\N{NO ENTRY} **NSFW image detected.**\n" \
			"This has been implemented to help " \
			"prevent the spread of illegal content.")


class Tags(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.discord_path = bot.path.discord
		self.files_path = bot.path.files
		self.code_api = bot.funcs.code_api
		self.code_block = bot.funcs.format_code
		self.find_member = bot.funcs.find_member
		self.get_lang = bot.funcs.get_lang
		self.bytes_download = bot.funcs._bytes_download
		self.f_api = bot.funcs.f_api
		self.get_attachment_image = bot.funcs.get_attachment_image
		self.hastebin = bot.funcs.hastebin
		self.get_text = bot.get_text
		self.execute = bot.mysql._execute
		self.gcv_request = bot.get_cog('Google').gcv_request
		self.command_messages = bot.command_messages

		self.nsfw_classification = ('LIKELY', 'VERY_LIKELY')
		# https://cloud.google.com/vision/docs/supported-files
		self.attachment_exts = (
			'.png', '.jpg', '.jpeg',
			'.gif', '.webp', '.heic',
			'.tiff', '.raw', '.ico',
			'.bmp'
		)


	async def is_nsfw(self, content, force=False):
		r = await self.gcv_request(content, "SAFE_SEARCH_DETECTION", force=force)
		if not r or not r['responses'][0]:
			raise Tag_Error("NSFW check failed, try again.")
		elif "error" in r['responses'][0]:
			err = r['responses'][0]['error']['message']
			raise Tag_Error(f"Google Vision API returned an error: {err}")

		load = r['responses'][0]['safeSearchAnnotation']
		if load['adult'] in self.nsfw_classification:
			raise Tag_NSFW


	async def nsfw_callback_check(self, msg):
		if msg.embeds:
			for e in msg.embeds:
				if e.url and e.type == "image":
					try:
						await self.is_nsfw(e.thumbnail.proxy_url, force=True)
					except Tag_NSFW as e:
						try:
							await msg.delete()
						except:
							# Message gone..
							pass
						else:
							await msg.channel.send(str(e))
					except Tag_Error:
						# Oh well, not gonna delete on API error
						pass

	# This is for tags with image LINKS
	# we check the embed discord resolves.
	async def nsfw_callback(self, message):
		try:
			def check(m, _):
				msgs = self.command_messages[message.id][2]
				return m.id in msgs
	
			_, msg = await self.bot.wait_for("message_edit", check=check, timeout=60)
		except asyncio.TimeoutError:
			return
		else:
			await self.nsfw_callback_check(msg)

	# Works for gifs too
	async def check_nsfw(self, content, message, attachments=None):
		if attachments:
			for attachment in attachments:
				# Will error if found
				await self.is_nsfw(attachment)

		# Prevent discord invis characters stripping
		if "http" in content.encode('ascii', 'ignore').decode():
			self.bot.loop.create_task(self.nsfw_callback(message))


	async def send(self, ctx, content:str, *args, **kwargs):
		if not content:
			return await ctx.send('\N{WARNING SIGN} `Tag returned empty output.`')

		kwargs['replace_mentions'] = kwargs.get('replace_mentions', True)
		kwargs['zero_width'] = True
		nsfw = kwargs.pop("nsfw", False)

		if isinstance(content, tuple):
			if nsfw:
				try:
					await self.check_nsfw(content[0], ctx.message, [x[0] for x in content[1]])
				except Tag_Error as e:
					return await ctx.send(str(e))

			# Reset to head after nsfw checks reading.
			for x in content[1]:
				x[0].seek(0)
			try:
				files = [discord.File(f, fn) for f, fn in content[1]]
				return await ctx.send(content[0], *args, files=files, **kwargs)
			finally:
				for f in files:
					f.close()
		elif nsfw:
			await self.check_nsfw(content, ctx.message)

		m = await ctx.send(content, *args, **kwargs)
		if nsfw:
			await self.nsfw_callback_check(m)
		return m

	def finduser(self, query, guild=None):
		discrim = None # If we know the user's discrim, we can prune our search. This gets used later on.
		# Check if finduser() has been supplied with something useful.
		match = re.findall(r"^<@!?(\d+)>$", query)
		if match: # Query is <!123456789123456789>
			# Exactly who we're looking for has been served on a silver platter. Marvellous.
			userid = int(match[0])
			user = discord.utils.get(guild.members, id=userid) if guild else self.bot.get_user(userid)
			return [user] # Done.
		elif re.search(r"^.*#\d{4}$", query): # Query is @user#0000
			# We don't have a user ID but we sure as hell can find one now we have the user's discrim and exact username.
			query = query[:-5] # Extract the username
			discrim = query[-4:] # Extract the discriminator
		# Create several sets which will have names sorted into them based on how close the name is to our query.
		exact = set()
		wrongcase = set()
		startswith = set()
		contains = set()
		# Get a list of users.
		users = guild.members if guild != None else self.bot.get_all_members()
		# Scan through the whole user list and insert them into the appropriete sets.
		for user in users:
			if discrim is not None and user.discriminator != discrim:
				# We know what the discrim is and this particular user's discrim doesn't match, discard them.
				continue
			match = self.check_match(query, user.name, user.display_name)
			if match == 4:
				exact.add(user)
			elif match == 3:
				wrongcase.add(user)
			elif match == 2:
				startswith.add(user)
			elif match == 1:
				contains.add(user)
		# Pick the best result and return it. Done.
		if exact:
			return list(exact)
		if wrongcase:
			return list(wrongcase)
		if startswith:
			return list(startswith)
		return list(contains)

	# This function returns a value from 0 to 4, describing how similar the query is to the username/nickname.
	# 0 = no match
	# 1 = string a contains string b
	# 2 = string a starts with string b
	# 3 = case-insensitive match
	# 4 = exact match
	@staticmethod
	def check_match(query, user, nick):
		if user == query or nick == query:
			return 4
		# Lower-case all the variables. The following conditions are case insensitive
		query = query.lower()
		user = user.lower()
		nick = nick.lower()
		if user == query or nick == query:
			return 3
		elif user.startswith(query) or nick.startswith(query):
			return 2
		elif query in user or query in nick:
			return 1
		return 0

	@staticmethod
	async def get_rand_members(guild, variables):
		if "__rand_members" not in variables:
			try:
				members = await guild.query_members(
					"", limit=1000, cache=False,
					presences=True
				)
			except:
				raise Tag_Find_Error('Timed out waiting for random member...')
			else:
				variables['__rand_members'] = members
				return members
		else:
			return variables['__rand_members']


	# Main parsing function (Returns a string)
	async def parse(self, ctx, tag:str, args:str, max_iterations:int=500):
		try:
			variables = {}
			# Set up private variables
			variables['__network_requests'] = 0

			result = await self.parse_inner(
				ctx, tag, args.split(" "),
				max_iterations, variables
			)
			parsed = result[0][:2000]
			files = result[3]
			if files:
				return (parsed, files)
			return parsed
		except checks.Nsfw:
			raise
		except Tag_NSFW as e:
			return str(e)
		except (Tag_Error, Tag_Script_Error, Tag_Find_Error) as e:
			return f"\N{WARNING SIGN} {str(e)}"
		except Exception as e:
			print(traceback.format_exc())
			return f"\N{WARNING SIGN} Parser error: `{str(e)}`"

	# Inner parsing function, use parse() instead. (Returns an array, [result, remaining_iterations, variables])
	async def parse_inner(self, ctx, tag, args, remaining_iterations, variables):
		result = ""
		buffer = ""
		files = []
		depth = 0
		for i, c in enumerate(tag):
			if remaining_iterations <= 0: # Iteration limit hit
				result += tag[:i]
				break
			if depth == 0: # Parsing non-script text
				if c == '{': # Start of script tag detected
					depth += 1
					continue
				# Plain text
				result += c
				# Prevent fork bombs
				if len(result) > 10000:
					raise Tag_Error("Tag attempted to use too much memory!")
			else:
				# Prevent abuse of networked script tags
				if variables['__network_requests'] > 15:
					raise Tag_Error(
						"Tag attempted to use too many network requests (> 15)!"
					)

				# Parse and execute script tag
				if c == '{':
					depth += 1
				if c == '}':
					depth -= 1
					if depth <= 0:
						if buffer.lower().startswith("ignore:"): # built-in ignore function
							result += buffer[7:]
						else:
							if not buffer.lower().startswith("note:"): # ignore tag comments
								# Split up multi-argument tags
								parsed_split = self.special_split(buffer)
								unparsed_split = parsed_split[:]
								remaining_iterations -= 1 # Decrement remaining_iterations
								# Parse each argument individually
								# Doing this arg-by-arg prevents {args}
								# from using unclosed curly braces to destroy complex tags
								for idx, arg in enumerate(parsed_split):
									sub_parse_result = await self.parse_inner(
										ctx, arg, args,
										remaining_iterations, variables
									)
									parsed_split[idx] = sub_parse_result[0]
									remaining_iterations = sub_parse_result[1]
									variables = sub_parse_result[2]
								# Finally execute the script tag
								if unparsed_split:
									func = unparsed_split[0].lower()
									# This was in script_function() but python
									# can't pass arguments as references,
									# so "variables" couldn't be shared
									if func == "set":
										if len(parsed_split) >= 3 and len(variables) < 100:
											var_name = parsed_split[1][:64]
											if var_name.startswith("__"):
												raise Tag_Error(
													"Private variable, cannot start with `__`."
												)
											variables[var_name] = "|".join(parsed_split[2:])[:2000]
									elif func == "eval":
										func = self.parse_inner(
											ctx, "|".join(parsed_split[1:]),
											args, remaining_iterations, variables
										)
										sub_parse_result = await func
										f = sub_parse_result[3]
										if f:
											files += f
										result += sub_parse_result[0]
										remaining_iterations = sub_parse_result[1]
										variables = sub_parse_result[2]
									# Limit to 4 attachments
									elif func in ("file", "attachment", "attach") and len(parsed_split) > 1 and len(files) <= 4:
										variables['__network_requests'] += 1

										url = parsed_split[1]
										fn = url.split('/')[-1] if len(parsed_split) <= 2 else parsed_split[2]
										if not any(x in fn.lower() for x in self.attachment_exts):
											raise Tag_Error("Only images/gifs are supported for attachments.")

										try:
											b = await self.bytes_download(url, proxy=True, limit=10**7)
										except asyncio.TimeoutError:
											raise Tag_Error("Attachment download timeout reached.")
										except LimitError as e:
											raise Tag_Error(str(e))
										except:
											b = False

										if b:
											files.append((b, fn))
									elif (func == "image" or func == "iscript") and len(parsed_split) > 1 and len(files) <= 4:
										variables['__network_requests'] += 1

										script = " ".join(parsed_split[1:])
										b = await self.f_api('parse_tag', text=script)
										if isinstance(b, str):
											raise Tag_Script_Error(b)
										files.append((b, 'image.png'))
									elif func in ("image2", "iscript2", "imagescript") and len(parsed_split) > 1 and len(files) <= 4:
										variables['__network_requests'] += 1

										script = " ".join(parsed_split[1:])
										b = await self.f_api('image_script', text=script)
										if isinstance(b, str):
											raise Tag_Script_Error(b)
										files.append((b, 'image.png'))
									else:
										try:
											func = self.script_function(ctx, func, parsed_split[1:],
																									unparsed_split[1:], buffer,
																									args, variables)
											result += await func
										except checks.Nsfw:
											raise
										except Tag_Script_Error as e:
											raise Tag_Script_Error(f"Error in `{{{func}}}`: `{str(e)}`")
						buffer = ""
						continue
				buffer += c
		result += buffer
		# done
		return [result, remaining_iterations, variables, files]

	# Except when an exception occurs, this ALWAYS returns an array with at least 2 items: [func, arg]
	def special_split(self, txt):
		r = []
		buffer = ""
		depth = 0
		for c in txt:
			if c == '{': # Voodoo witchcraft to stop the splitter from messing with tag scripts
				depth += 1
			else:
				if c == '}':
					depth -= 1
			if depth == 0 and ((c == ':' and not r) or (c == '|' and r)):
				r.append(buffer)
				buffer = ""
			else:
				buffer += c
		# add buffer remainder
		if buffer:
			r.append(buffer)
		# ensure the result contains at least 2 items
		while len(r) < 2:
			r.append("")
		# done
		return r

	# Custom scripts go in here
	# Use args for script tags like {choose} and {if}, so the result doesn't have to be parsed again
	# Use unparsed_args for script tags like {lua}, so it doesn't mess with the code
	# full_args is a string containing the entire contents of the script tag. There's little reason to use this for script tags.
	async def script_function(self, ctx, func, args, unparsed_args, full_args, tag_args, variables):
		if (func == "name" or func == "user") and (len(args) == 1 and args[0] == ""):
			return ctx.author.name
		elif func == "userid":
			return str(ctx.author.id)
		elif func == "id":
			return str(ctx.author.id)
		elif func == "mention":
			return ctx.author.mention
		elif func == "nick":
			return ctx.author.display_name
		elif func == "discrim":
			return str(ctx.author.discriminator)
		elif func == "guild" or func == "server":
			return ctx.guild.name if ctx.guild else "Direct Message"
		elif func in ("guildid", "serverid", "sid", "gid"):
			return str(ctx.guild.id) if ctx.guild else "0"
		elif func == "guildcount" or func == "servercount" or func == "membercount":
			return str(ctx.guild.member_count) if ctx.guild else "2"
		elif func == "channel":
			return ctx.channel.name if ctx.guild else "Direct Message"
		elif func == "channelid":
			return str(ctx.channel.id) if ctx.channel else "0"
		elif func.startswith("randuser"):
			members = await self.get_rand_members(ctx.guild, variables)
			member = random.choice(members)
			if func.endswith("id"):
				return str(member.id) if ctx.guild else str(ctx.author.id)
			return member.display_name if ctx.guild else ctx.author.display_name
		elif func.startswith("randonline"):
			members = await self.get_rand_members(ctx.guild, variables)
			member = random.choice([m for m in members if m.status is discord.Status.online])
			if func.endswith("id"):
				return str(member.id) if ctx.guild else str(ctx.author.id)
			return member.display_name if ctx.guild else ctx.author.display_name
		elif func == "randchannel":
			return random.choice(list(ctx.guild.channels)).mention if ctx.guild else ctx.channel.mention
		elif func == "avatar":
			if len(args) == 1 and args[0] == "":
				return str(ctx.author.avatar_url)
			else:
				user = await self.find_member(ctx.message, args[0])
				if user:
					return str(user.avatar_url)
			return ""
		elif func == "nsfw" and ctx.guild:
			if not ctx.channel.is_nsfw():
				raise checks.Nsfw()
			return ""
		# Username and nickname searching
		elif (func == "name" or func == "user" or func == "nick") and args:
			query = args[0]
			if not query:
				return ""
			users = None
			if ctx.guild is not None:
				users = self.finduser(query, ctx.guild)
			if users is None or not users:
				users = self.finduser(query)
			if not users:
				raise Tag_Find_Error('No user(s) found with "{0}"'.format(query))
			elif len(users) > 1:
				out = 'Multiple users found with "{0}":'.format(query)
				for u in users[:6]:
					out += "\n - {}".format(str(u))
				if len(users) > 6:
					out += "\n and {0} more.".format(str(len(users) - 6))
				raise Tag_Find_Error(out)
			return users[0].display_name if func == "nick" else users[0].name
		# Tag arguments
		elif func == "args":
			return " ".join(tag_args)
		elif func == "argslen":
			return str(len(tag_args))
		elif func == "arg" and len(args) >= 1 and args[0].isdigit():
			arg_index = int(args[0])
			if arg_index < len(tag_args):
				return tag_args[arg_index]
			return ""
		# String functions
		elif func == "upper":
			return "|".join(args).upper()
		elif func == "lower":
			return "|".join(args).lower()
		elif func == "len" or func == "length":
			return str(len("|".join(args)))
		elif func == "url":
			return quote("|".join(args))
		# Replace
		elif (func == "replace" or func == "replaceregex") and len(args) >= 3:
			# Get the pattern, in, and with args.
			cardinal_args = ["", "", ""] # Contains the following sequence: pattern, in, with
			addto = 0
			for i, c in enumerate(args):
				if c.startswith("pattern:"):
					addto = 0
					cardinal_args[0] += c[8:]
				elif c.startswith("with:"):
					addto = 1
					cardinal_args[1] += c[5:]
				elif c.startswith("in:"):
					addto = 2
					cardinal_args[2] += c[3:]
				else:
					cardinal_args[addto] += c if i == 0 else f"|{c}"
			# return re.sub(cardinal_args[0], cardinal_args[1], cardinal_args[2], \
			# 							flags=re.S|re.X) \
			# 			 if func == "replaceregex" else \
			# 			 cardinal_args[2].replace(cardinal_args[0], cardinal_args[1])
			return cardinal_args[2].replace(cardinal_args[0], cardinal_args[1])
		# Numeric functions
		elif func == "math":
			result = 0
			setr = True # This is used to set result to the first number before doing operations to it.
			op = 0 # Mathematic operation modes: 0=addition, 1=subtraction, 2=multiplication, 3=division, 4=modulo
			for arg in args:
				if arg.isdigit():
					iarg = int(arg)
					if setr:
						result = iarg
						setr = False
					else:
						if op == 0:
							result += iarg
						elif op == 1:
							result -= iarg
						elif op == 2:
							result *= iarg
						elif op == 3:
							result /= iarg
						elif op == 4:
							result %= iarg
				elif arg == "+":
					op = 0
				elif arg == "-":
					op = 1
				elif arg == "*":
					op = 2
				elif arg == "/":
					op = 3
				elif arg == "%":
					op = 4
			return str(result)
		# RNG functions
		elif func == "choose":
			return random.choice(args)
		elif func == "range" and len(args) >= 2:
			try:
				return str(random.randint(int(args[0]), int(args[1])))
			except ValueError:
				return f"{{{full_args}}}"
		# Logical and memory functions
		elif func == "get" and args:
			if args[0].startswith("__"):
				raise Tag_Error(
					"Private variable, cannot start with `__`."
				)
			return str(variables.get(args[0], ''))
		elif func == "if" and len(args) >= 4:
			# Get the values to be compared
			s1 = args[0]
			s2 = args[2]
			comparison = args[1]
			# Get the values to return
			then_ = ""
			else_ = ""
			add2else = False
			for i,c in enumerate(args[3:]):
				if c.startswith("then:"):
					add2else = False
					then_ += c[5:]
				elif c.startswith("else:"):
					add2else = True
					else_ += c[5:]
				else:
					t = f"|{c}"
					if add2else:
						else_ += t
					else:
						then_ += t
			# Compare s1 and s2 using comparison
			if comparison == "=":
				return then_ if s1 == s2 else else_
			# elif comparison == "?":
			# 	return then_ if re.search(s2, s1) else else_
			try:
				i1 = float(s1)
				i2 = float(s2)
				if comparison == "<":
					return then_ if i1 < i2 else else_
				elif comparison == "<=":
					return then_ if i1 <= i2 else else_
				elif comparison == ">":
					return then_ if i1 > i2 else else_
				elif comparison == ">=":
					return then_ if i1 >= i2 else else_
				elif comparison == "~":
					return then_ if i1 * 100 == i2 * 100 else else_
			except ValueError:
				if comparison == "~":
					return then_ if s1.lower() == s2.lower() else else_
				return else_
		elif func in ("lattach", "lattachment", "last_attachment") \
				 and (len(args) == 1 and not args[0]):
			variables['__network_requests'] += 1

			return await self.get_attachment_image(ctx, check=None) or ""
		elif (func == "hastebin" or func == "haste") and args[0]:
			variables['__network_requests'] += 1

			return await self.hastebin(args[0])
		elif (func == "text" or func == "download") and args[0]:
			variables['__network_requests'] += 1

			url = f"http://{args[0]}" if not args[0].startswith('http') else args[0]
			return await self.get_text(
				url, timeout=6, proxy=True,
				discord_limit=True
			) or ""
		elif func == "prefix" and (len(args) == 1 and args[0] == ""):
			return (await get_prefix(self.bot, ctx.message))[0][0]
		elif func == "substring" and len(args) >= 3:
			start = int(args[1])
			end = int(args[2])
			return args[0][start:end]
		elif func == "code" and args[0]:
			if len(args) > 1:
				lang = args[1]
			else:
				lang = "fix"
			return self.code_block("|".join(args), lang)
		# Rextester
		# always leave for last
		elif args and self.get_lang(func):
			variables['__network_requests'] += 1

			r = await self.code_api(func, args[0], fmt=False)
			return r[0] or r[1]
		# Default value for unknown tag functions
		return f"{{{full_args}}}"

	# Modified 08/15/2020 to disable global tags
	async def get_tag(self, ctx, tag, raw=False, nsfw_check=False, return_guild=False):
		sql = "SELECT * FROM `tags` WHERE tag=%s AND "
		sql += "(guild_created=%s OR guild=%s)"
		args = (tag, ctx.guild.id, ctx.guild.id)
		q = await self.cursor.execute(sql, args)
		r = await q.fetchall()
		if raw:
			return r
		if not r:
			await ctx.send(f'\N{NO ENTRY} Tag "{tag}" does not exist!')
			return False
		# Either the first guild tag
		if len(r) > 1:
			r = next(x for x in r if x['guild'])
		# or the first "global" tag
		else:
			r = r[0]
		content = r['content']
		if nsfw_check and (ctx.guild and r"{nsfw}" in content and not ctx.channel.is_nsfw()):
			raise checks.Nsfw()

		if return_guild:
			return r
		return content

	@commands.group(invoke_without_command=True, aliases=['t', 'ta', 'tags'])
	@commands.guild_only()
	@commands.cooldown(4, 2, commands.BucketType.guild)
	async def tag(self, ctx, txt:str, *, after:str=""):
		"""Base command for tags, call it with a valid tag to display a tag"""
		content = await self.get_tag(ctx, txt)
		if not content:
			return
		try:
			parsed = await asyncio.wait_for(self.parse(ctx, content, after), timeout=30, loop=self.bot.loop)
		except asyncio.TimeoutError:
			await ctx.send('\N{WARNING SIGN} `Tag timed out...`')
		else:
			await self.send(ctx, parsed, nsfw=True)

	async def name_check(self, ctx, name):
		#owner or notsoman maintainer
		if not await self.bot.is_owner(ctx.author) and ctx.author.id != 125459693685440513:
			if name.startswith(r'{') and name.endswith(r'}'):
				return await ctx.send('\N{NO ENTRY} Tag names cannot start with `{` and end with `}`.')

	@tag.command(name='add', aliases=['create', 'make'])
	@commands.guild_only()
	@commands.cooldown(1, 15, commands.BucketType.guild)
	async def tag_add(self, ctx, tag:str=None, *, txt:str=""):
		"""Add a tag"""
		if tag is None:
			return await ctx.send("Error: Invalid Syntax\nPlease input the tags name\n`.tag add <tag_name> <--this one <tag_content>`")
		elif not txt and not ctx.message.attachments:
			return await ctx.send("Error: Invalid Syntax\nPlease input something for the tag to contain\n`.tag add <tag_name> <tag_content> <--this one`")
		elif len(tag) > 60:
			return await ctx.send("\N{NO ENTRY} `Tag name limit (<= 60).`")
		elif await self.name_check(ctx, tag):
			return

		sql = f"SELECT COUNT(`user`) as Count FROM `tags` WHERE user={ctx.author.id}"
		r = await (await self.cursor.execute(sql)).fetchone()
		if r['Count'] >= 5000:
			return await ctx.send("\N{NO ENTRY} `Tag limit reached (5000).`")

		for a in ctx.message.attachments:
			txt += f"{{attach:{a.proxy_url}}}"
		gid = ctx.guild and ctx.guild.id
		result = await self.get_tag(ctx, tag, raw=True)
		if not result:
			sql = "INSERT INTO `tags` (`user`, `tag`, `content`, `guild_created`) VALUES (%s, %s, %s, %s)"
			await self.cursor.execute(sql, (ctx.author.id, tag, txt, gid))
			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Added Tag \"{tag}\"")
		# elif gid and len(result) == 1 and not result[0]['guild'] \
		# 		 and result[0]['guild_created'] != gid:
		# 	sql = "INSERT INTO `tags` (`guild`, `user`, `tag`, `content`) VALUES (%s, %s, %s, %s)"
		# 	await self.cursor.execute(sql, (gid, ctx.author.id, tag, txt))
		# 	return await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Added Guild Tag \"{tag}\"")
		else:
			await ctx.send(f"\N{NO ENTRY} Tag \"{tag}\" already exists!")

	# @tag.command(name='guildadd', aliases=['gcreate', 'gmake', 'gadd'])
	# @commands.guild_only()
	# @commands.cooldown(1, 15, commands.BucketType.guild)
	# async def tag_guildadd(self, ctx, tag:str=None, *, txt:str=""):
	# 	"""Add a guild tag"""
	# 	if tag is None:
	# 		return await ctx.send("Error: Invalid Syntax\nPlease input the tags name\n`.tag add <tag_name> <--this one <tag_content>`")
	# 	elif not txt and not ctx.message.attachments:
	# 		return await ctx.send("Error: Invalid Syntax\nPlease input something for the tag to contain\n`.tag add <tag_name> <tag_content> <--this one`")
	# 	elif len(tag) > 60:
	# 		return await ctx.send("\N{NO ENTRY} `Tag name limit (<= 60).`")
	# 	elif await self.name_check(ctx, tag):
	# 		return
	# 	for a in ctx.message.attachments:
	# 		txt += f"{{attach:{a.proxy_url}}}"
	# 	gid = ctx.guild.id
	# 	sql = "SELECT tag FROM `tags` WHERE tag=%s AND (guild=%s OR guild_created=%s)"
	# 	q = await self.cursor.execute(sql, (tag, gid, gid))
	# 	if await q.fetchone():
	# 		return await ctx.send(f"\N{NO ENTRY} Tag \"{tag}\" already exists!")
	# 	sql = "INSERT INTO `tags` (`guild`, `user`, `tag`, `content`) VALUES (%s, %s, %s, %s)"
	# 	await self.cursor.execute(sql, (gid, ctx.author.id, tag, txt))
	# 	return await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Added Guild Tag \"{tag}\"")

	async def remove_global_tag(self, ctx, tag):
		sql = "SELECT tag FROM `tags` WHERE tag=%s AND user=%s AND guild_created=%s"
		args = (tag, ctx.author.id, ctx.guild.id)
		q = await self.cursor.execute(sql, args)
		if not await q.fetchone():
			await ctx.send(f"\N{CROSS MARK} Tag \"{tag}\" does not exist or you don't own it!")
		else:
			sql = "DELETE FROM `tags` WHERE tag=%s AND user=%s AND guild_created=%s"
			await self.cursor.execute(sql, args)
			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Removed Tag \"{tag}\"")

	@tag.group(name='remove', aliases=['delete'], invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.user)
	async def tag_remove(self, ctx, *, txt:str=None):
		""""Remove a tag you own"""
		if txt is None:
			return await ctx.send("Invalid Syntax\nPlease input something to remove from your tags\n`.tag remove <tag_name>`")
		elif ctx.guild is None:
			return await self.remove_global_tag(ctx, txt)
		sql = "SELECT guild FROM `tags` WHERE guild=%s AND user=%s AND tag=%s"
		q = await self.cursor.execute(sql, (ctx.guild.id, ctx.author.id, txt))
		if not await q.fetchone():
			await self.remove_global_tag(ctx, txt)
		else:
			sql = "DELETE FROM `tags` WHERE guild=%s AND user=%s AND tag=%s"
			await self.cursor.execute(sql, (ctx.guild.id, ctx.author.id, txt))
			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Removed Tag \"{txt}\"")

	@tag_remove.command(name='all')
	@commands.cooldown(1, 30, commands.BucketType.user)
	async def tag_remove_all(self, ctx):
		x = await ctx.send(f'\N{WARNING SIGN} Are you **SURE** you want to remove __all__ your tags?')
		def check(m):
			return m.channel == ctx.channel and m.author == ctx.author and m.content.lower() in ('y', 'yes')
		try:
			_ = await self.bot.wait_for('message', check=check, timeout=30)
		except asyncio.TimeoutError:
			await x.delete()
			return await ctx.send('\N{NO ENTRY} `Took too long to confirm.`', delete_after=5)
		sql = "DELETE FROM `tags` WHERE user=%s"
		await self.cursor.execute(sql, (ctx.author.id,))
		await ctx.send("\N{WHITE HEAVY CHECK MARK} Removed `all` of your tags")

	@tag.command(name='edit')
	@commands.guild_only()
	@commands.cooldown(1, 3, commands.BucketType.user)
	async def tag_edit(self, ctx, tag:str=None, *, txt:str=""):
		"""Edit a tag you own"""
		if tag is None:
			return await ctx.send("Invalid Syntax\nPlease input the tags name\n`.tag edit <tag_name> <--this one <tag_edited_content>`")
		elif not txt and not ctx.message.attachments:
			return await ctx.send("Invalid Syntax\nPlease input something to edit the tag with\n`.tag edit <tag_name> <tag_edited_content> <--this one`")
		for a in ctx.message.attachments:
			txt += f"{{attach:{a.proxy_url}}}"
		sql = "SELECT tag FROM `tags` WHERE tag=%s AND user=%s AND guild_created=%s"
		q = await self.cursor.execute(sql, (tag, ctx.author.id, ctx.guild.id))
		try:
			if not await q.fetchone():
				sql = "SELECT guild FROM `tags` WHERE guild=%s AND tag=%s AND user=%s"
				q = await self.cursor.execute(sql, (ctx.guild.id, tag, ctx.author.id))
				assert await q.fetchone()
				sql = "UPDATE `tags` SET content=%s WHERE guild=%s AND tag=%s AND user=%s"
				await self.cursor.execute(sql, (txt, ctx.guild.id, tag, ctx.author.id))
				await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Edited tag \"{tag}\"")
			else:
				sql = "UPDATE `tags` SET content=%s WHERE tag=%s AND user=%s AND guild_created=%s"
				await self.cursor.execute(sql, (txt, tag, ctx.author.id, ctx.guild.id))
				await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Edited tag \"{tag}\"")
		except AssertionError:
			await ctx.send(f"\N{CROSS MARK} Tag \"{tag}\" does not exist or you don't own it!")

	# @tag.command(name='gview', aliases=['graw'])
	# @commands.cooldown(1, 3, commands.BucketType.guild)
	# async def tag_gview(self, ctx, *, tag:str):
	# 	"""Raw text of a global tag"""
	# 	content = await self.get_tag(ctx, tag, nsfw_check=True, global_only=True)
	# 	if content:
	# 		await self.send(ctx, f"**Raw Global Tag \"{tag}\"**\n{content}", nsfw=True)

	# @tag.command(name='gview2', aliases=['graw2'])
	# @commands.cooldown(1, 3, commands.BucketType.guild)
	# async def tag_gview2(self, ctx, *, tag:str):
	# 	"""Raw text of a global tag in a codeblock"""
	# 	content = await self.get_tag(ctx, tag, nsfw_check=True, global_only=True)
	# 	if content:
	# 		content = self.code_block(content.replace('`', r'\`'), None)
	# 		await self.send(ctx, f"**Raw Global Tag \"{tag}\"**\n{content}", nsfw=True)

	# @tag.command(name='gview3', aliases=['graw3'])
	# @commands.cooldown(1, 3, commands.BucketType.guild)
	# async def tag_gview3(self, ctx, *, tag:str):
	# 	"""Raw text of a global tag in hastebin"""
	# 	content = await self.get_tag(ctx, tag, nsfw_check=True, global_only=True)
	# 	if content:
	# 		content = await self.hastebin(content)
	# 		await self.send(ctx, f"**Raw Global Tag \"{tag}\"**\n{content}")

	@tag.command(name='view', aliases=['raw'])
	@commands.guild_only()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def tag_view(self, ctx, *, tag:str):
		"""Raw text of a tag"""
		content = await self.get_tag(ctx, tag, nsfw_check=True)
		if content:
			await self.send(ctx, f"**Raw Tag \"{tag}\"**\n{content}", nsfw=True)

	@tag.command(name='view2', aliases=['raw2'])
	@commands.guild_only()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def tag_view2(self, ctx, *, tag:str):
		"""Raw text of your tag in a codeblock"""
		content = await self.get_tag(ctx, tag, nsfw_check=True)
		if content:
			content = self.code_block(content.replace('`', r'\`'), None)
			await self.send(ctx, f"**Raw Tag \"{tag}\"**\n{content}", nsfw=True)

	@tag.command(name='view3', aliases=['raw3'])
	@commands.guild_only()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def tag_view3(self, ctx, *, tag:str):
		"""Raw text of your tag in hastebin"""
		content = await self.get_tag(ctx, tag, nsfw_check=True)
		if content:
			content = await self.hastebin(content)
			await self.send(ctx, f"**Raw Tag \"{tag}\"**\n{content}")

	@tag.command(name='list', aliases=['mytags'])
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def tag_list(self, ctx, user:discord.User=None):
		"""List all your tags or a users"""
		user = user or ctx.author
		sql = f'SELECT * FROM `tags` WHERE user={user.id} AND (guild_created={ctx.guild.id} ' \
					f'OR guild={ctx.guild.id}) ORDER BY `id` DESC'

		# limit results to 5000
		sql += " LIMIT 5000"
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await self.send(ctx, "\N{NO ENTRY} User `{0}` does not own any tags!".format(user))
		entries = []
		for s in result:
			tag = s['tag'][:60]
			entries.append(f'"{tag}"')
		try:
			p = Pages(ctx, entries=entries, per_page=20)
			p.embed.title = 'Tag List'
			p.embed.color = 0x738bd7
			p.embed.set_author(name=user.display_name, icon_url=user.avatar_url or user.default_avatar_url)
			await p.paginate()
		except CannotPaginate:
			await self.send(ctx, "**List of {0}'s Tags**\n{1}".format(user.name, ', '.join(entries)))

	# @tag.command(name='glist', aliases=['guildtags'])
	# @commands.cooldown(1, 15, commands.BucketType.guild)
	# @commands.guild_only()
	# async def tag_glist(self, ctx):
	# 	"""List all guild tags"""
	# 	sql = f'SELECT * FROM `tags` WHERE guild={ctx.guild.id}'
	# 	q = await self.cursor.execute(sql)
	# 	result = await q.fetchall()
	# 	if not result:
	# 		return await self.send(ctx, "\N{NO ENTRY} No guild tags exit!")
	# 	entries = []
	# 	for s in result:
	# 		entries.append(f"\"{s['tag']}\" - `{s['user']}`")
	# 	try:
	# 		p = Pages(
	# 			ctx, entries=entries, per_page=20,
	# 			extra_info="Number in brackets is the tag owners User ID."
	# 		)
	# 		p.embed.title = 'Guild Tag List'
	# 		p.embed.color = 0x738bd7
	# 		p.embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
	# 		await p.paginate()
	# 	except CannotPaginate:
	# 		await self.send(ctx, "**Guild tags**\n{1}".format(', '.join(entries)))


	# @tag_list.command(name='all', aliases=['alltags'])
	# @commands.cooldown(1, 300, commands.BucketType.guild)
	# async def tag_list_all(self, ctx):
	# 	"""List All Tags"""
	# 	try:
	# 		sql = 'SELECT tag,guild FROM `tags`'
	# 		q = await self.cursor.execute(sql)
	# 		result = await q.fetchall()
	# 		if not result:
	# 			return await self.send(ctx, "\N{NO ENTRY} There are no tags!")
	# 		results = ""
	# 		for s in result:
	# 			if s['guild']:
	# 				results += 'Guild Tag ({0}): {1}\n'.format(s['guild'], s['tag'])
	# 			else:
	# 				results += s['tag'] + "\n"
	# 		txt = BytesIO(results.encode())
	# 		txt.seek(0)
	# 		await ctx.send(file=txt, content='\N{WARNING SIGN} All tags!', filename='alltags.txt')
	# 	except Exception as e:
	# 		await self.send(ctx, e)

	@tag.command(name='owner', aliases=['whoowns', 'whomade'])
	@commands.guild_only()
	@commands.cooldown(1, 3, commands.BucketType.user)
	async def tag_owner(self, ctx, *, txt:str):
		"""Who owns a tag?"""
		r = await self.get_tag(ctx, txt, raw=True)
		if not r:
			return await ctx.send(f"\N{CROSS MARK} Tag \"{txt}\" does not exist!")
		if len(r) > 1:
			r =  next(x for x in r if x['guild'])
		else:
			r = r[0]
		tag_owner = r['user']
		user = await self.find_member(ctx.message, tag_owner)
		await ctx.send(f"\N{INFORMATION SOURCE} " \
									 f"Tag \"{txt}\" is owned by `{user} ({tag_owner})`")

	# @tag.command(name='globalowner', aliases=['gwhoowns','gowner', 'gwhomade'])
	# @commands.cooldown(1, 3, commands.BucketType.user)
	# async def tag_globalowner(self, ctx, *, txt:str):
	# 	"""Who owns a global tag? Useful when a guild tag overrides it."""
	# 	sql = "SELECT user,guild FROM `tags` WHERE tag=%s AND guild is NULL"
	# 	q = await self.cursor.execute(sql, (txt,))
	# 	r = await q.fetchone()
	# 	if not r:
	# 		return await ctx.send(f"\N{CROSS MARK} Tag \"{txt}\" does not exist!")
	# 	tag_owner = r['user']
	# 	user = await self.find_member(ctx.message, tag_owner)
	# 	await ctx.send(f"\N{INFORMATION SOURCE} Tag \"{txt}\" is owned by `{user} ({tag_owner})`")

	@tag.command(name='random')
	@commands.guild_only()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def tag_random(self, ctx, *, args:str=""):
		"""Random tag"""
		# does not support guild tags, but fast!
		# TODO: also add the guilds own tags
		sql = """
		SELECT tag,content
			FROM tags AS r1 JOIN
					(SELECT CEIL(RAND() *
												(SELECT MAX(id)
														FROM tags)) AS id)
						AS r2
		WHERE (r1.guild={0} OR r1.guild_created={0}) AND r1.id >= r2.id
		ORDER BY r1.id ASC
		LIMIT 1
		"""
		q = await self.execute(sql.format(ctx.guild.id), fetch=True)
		result = await q.fetchone()
		tag = result['tag']
		parsed = await self.parse(ctx, result['content'], args)
		m = "**Tag: {0}**\n{1}"
		if isinstance(parsed, tuple):
			m = (m.format(tag, parsed[0]), parsed[1])
		else:
			m = m.format(tag, parsed)
		await self.send(ctx, m, nsfw=True)

	@tag.group(name='search', aliases=['find'])
	@commands.guild_only()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def tag_search(self, ctx, *, txt:str):
		"""Search for a tag"""
		txt = txt.replace("%", "").strip("_")
		if len(txt) <= 2:
			return await ctx.send("\N{NO ENTRY} Query must be atleast 3 characters.")
		sql = 'SELECT * FROM `tags` WHERE tag LIKE %s AND (guild_created=%s OR guild=%s)'
		sql += " LIMIT 100"
		l = f'%{txt}%'
		q = await self.cursor.execute(sql, (l, ctx.guild.id, ctx.guild.id))
		result = await q.fetchall()
		if not result:
			return await ctx.send(
				f"\N{HEAVY EXCLAMATION MARK SYMBOL} No results found for tags like `{txt}`."
			)
		entries = []
		for s in result:
			tag = s['tag']
			entry = f'"{tag}"'
			if s['user'] == ctx.author.id:
				entry += " (Your Tag)"
			# elif ctx.guild and s['guild'] == ctx.guild.id:
			# 	entry += " (Guild Tag)"
			entries.append(entry)
		try:
			p = Pages(ctx, entries=entries, per_page=20)
			p.embed.title = 'Tag Search Results'
			p.embed.color = 0x738bd7
			p.embed.set_author(
				name=ctx.author.display_name,
				icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url
			)
			await p.paginate()
		except CannotPaginate:
			await self.send(ctx, "\N{WHITE HEAVY CHECK MARK} Results:\n{0}".format('\n'.join(entries[:50])))

	@tag.group(name='forceremove', invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_server=True)
	async def tag_fm(self, ctx, *, txt:str):
		"""Force remove a tag"""
		r = await self.get_tag(ctx, txt, return_guild=True)
		if r:
			sql = "DELETE FROM `tags` WHERE id=%s"
			await self.cursor.execute(sql, (r['id'],))
			await self.send(ctx, "\N{WHITE HEAVY CHECK MARK} Force Removed Tag \"{0}\"".format(txt))

	@tag_fm.command(name='user')
	@commands.guild_only()
	@commands.is_owner()
	async def tag_fm_user(self, ctx, user:discord.User, *, txt:str):
		owner_id = user.id
		sql = "SELECT tag FROM `tags` WHERE tag=%s AND user=%s AND guild IS NULL LIMIT 1"
		q = await self.cursor.execute(sql, (txt, owner_id))
		if not await q.fetchone():
			return await self.send(ctx, "\N{CROSS MARK}	Tag \"{0}\" by user `{1}` does not exist!".format(txt, user.name))
		else:
			sql = "SELECT guild FROM `tags` WHERE guild=%s AND user=%s AND tag=%s LIMIT 1"
			q = await self.cursor.execute(sql, (ctx.guild.id, owner_id, txt))
			if not await q.fetchone():
				sql = "DELETE FROM `tags` WHERE tag=%s AND user=%s AND guild IS NULL"
				await self.cursor.execute(sql, (txt, owner_id))
			else:
				sql = "DELETE FROM `tags` WHERE guild=%s AND user=%s tag=%s"
				await self.cursor.execute(sql, (ctx.guild.id, owner_id, txt))
		await self.send(ctx, "\N{WHITE HEAVY CHECK MARK} Force Removed Tag \"{0}\" owned by `{1}`".format(txt, user.name))

	@tag.command(name='gift')
	@commands.guild_only()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def tag_gift(self, ctx, tag:str, *, user:discord.User):
		"""Gift/Give a Tag to a User\nTransfer Ownership"""
		if user == ctx.author:
			return await ctx.send("\N{NO ENTRY} `Can't gift tags to yourself loser.`")
		elif user.bot:
			return await ctx.send("\N{NO ENTRY} `no butts.`")

		sql = "SELECT guild FROM `tags` WHERE guild=%s AND tag=%s AND user=%s"
		q = await self.cursor.execute(sql, (ctx.guild.id, tag, ctx.author.id))
		r = await q.fetchone()
		if not r:
			sql = "SELECT tag FROM `tags` WHERE tag=%s AND user=%s AND guild_created=%s"
			q = await self.cursor.execute(sql, (tag, ctx.author.id, ctx.guild.id))
			r = await q.fetchone()
		if not r:
			m = f'\N{CROSS MARK} Tag "{tag}" does not exist or you don\'t own it!'
			return await self.send(ctx, m)

		mentions = discord.AllowedMentions(users=[ctx.author, user])
		await ctx.send(
			f'\N{WRAPPED PRESENT} {user.mention}, {ctx.author.mention} ' \
			f'wants to gift you tag "{tag}".\nIf you\'d like to accept respond with **yes**!',
			replace_mentions=False, allowed_mentions=mentions
		)

		def check(m):
			return m.channel == ctx.channel and m.author == user and m.content.lower() in ('y', 'yes')

		try:
			_ = await self.bot.wait_for('message', check=check, timeout=30)
		except asyncio.TimeoutError:
			return await ctx.send('\N{NO ENTRY} `Gift recipient took too long to respond.`')

		m = "\N{WHITE HEAVY CHECK MARK} Gifted Tag \"{0}\" to `{1}`"
		is_guild = "guild" in r
		if is_guild:
			sql = "UPDATE `tags` SET user=%s WHERE guild=%s AND tag=%s AND user=%s"
			await self.cursor.execute(sql, (user.id, ctx.guild.id, tag, ctx.author.id))
		else:
			sql = "UPDATE `tags` SET user=%s WHERE tag=%s AND user=%s AND guild_created=%s"
			await self.cursor.execute(sql, (user.id, tag, ctx.author.id, ctx.guild.id))

		await self.send(ctx, m.format(tag, user))

	@tag.command(name='rename')
	@commands.guild_only()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def tag_rename(self, ctx, tag:str, new:str):
		"""Rename your tag"""
		if len(new) > 60:
			return await ctx.send("\N{NO ENTRY} `Tag name limit (<= 60).`")
		elif await self.name_check(ctx, new):
			return
		# Make sure tag they want to rename exists
		sql = "SELECT guild FROM `tags` WHERE guild=%s AND tag=%s AND user=%s"
		q = await self.cursor.execute(sql, (ctx.guild.id, tag, ctx.author.id))
		r = await q.fetchone()
		if not r:
			sql = "SELECT tag FROM `tags` WHERE tag=%s AND user=%s AND guild IS NULL"
			q = await self.cursor.execute(sql, (tag, ctx.author.id))
			r = await q.fetchone()
			if not r:
				return await ctx.send(f"\N{CROSS MARK} Tag \"{tag}\" does not exist or you don't own it!")
		# Make sure the renamed tag doesn't exist
		sql = "SELECT tag FROM `tags` WHERE tag=%s AND (guild_created=%s OR guild=%s) LIMIT 1"
		q = await self.cursor.execute(sql, (new, ctx.guild.id, ctx.guild.id))
		if await q.fetchone():
			return await ctx.send(f'\N{NO ENTRY} Tag with name \"{new}\" already exists.')

		if "guild" not in r:
			sql = "UPDATE `tags` SET tag=%s WHERE tag=%s AND user=%s AND guild_created=%s"
			await self.cursor.execute(sql, (new, tag, ctx.author.id, ctx.guild.id))
			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Renamed Tag \"{tag}\" to {new}")
		else:
			sql = "UPDATE `tags` SET tag=%s WHERE guild=%s AND tag=%s AND user=%s"
			await self.cursor.execute(sql, (new, ctx.guild.id, tag, ctx.author.id))
			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Renamed Tag \"{tag}\" to {new}")

	# @tag.command(name='global')
	# @commands.cooldown(1, 3, commands.BucketType.guild)
	# async def tag_global(self, ctx, tag:str, *, after:str=""):
	# 	"""Force return a global tag"""
	# 	sql = "SELECT content FROM `tags` WHERE tag=%s AND guild IS NULL"
	# 	q = await self.cursor.execute(sql, (tag,))
	# 	result = await q.fetchone()
	# 	if not result:
	# 		return await ctx.send(f"\N{NO ENTRY} Tag \"{tag}\" does not exist!")
	# 	try:
	# 		parsed = await asyncio.wait_for(self.parse(ctx, result['content'], after), timeout=30, loop=self.bot.loop)
	# 	except asyncio.TimeoutError:
	# 		await ctx.send('\N{WARNING SIGN} `Tag timed out...`')
	# 	else:
	# 		await self.send(ctx, parsed, nsfw=True)

	@tag.command(name='forcensfw', aliases=['forcen'])
	@commands.is_owner()
	async def tag_forcensfw(self, ctx, *tags:str):
		for tag in tags:
			sql = "SELECT tag FROM `tags` WHERE tag=%s AND guild IS NULL"
			q = await self.cursor.execute(sql, (tag,))
			check_result = await q.fetchall()
			if not check_result:
				await self.send(ctx, "\N{CROSS MARK} Tag \"{0}\" does not exist!".format(tag))
				continue
			else:
				sql = "SELECT id FROM `tags` WHERE guild=%s AND tag=%s"
				q = await self.cursor.execute(sql, (ctx.guild.id, tag))
				global_result = await q.fetchall()
				sql = "UPDATE `tags` SET content=CONCAT(content, '{nsfw}') WHERE tag=%s"
				if not global_result:
					await self.cursor.execute(f"{sql} AND guild IS NULL", (tag,))
					await self.send(ctx, "\N{WHITE HEAVY CHECK MARK} Forced NSFW for tag \"{0}\"".format(tag))
				else:
					await self.cursor.execute(f"{sql} AND guild=%s", (tag, ctx.guild.id))
					await self.send(ctx, "\N{WHITE HEAVY CHECK MARK} Forced NSFW for guild tag \"{0}\"".format(tag))

def setup(bot):
	bot.add_cog(Tags(bot))
