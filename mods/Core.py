import asyncio
import datetime
import re
import signal
from collections import deque
from functools import partial
from io import BytesIO
from os.path import isfile
from string import ascii_letters
from time import time

#pylint: disable=import-error, E0611
import discord
from discord.ext import commands
from discord.ext.commands.view import StringView

import sentry_sdk

from mods.cog import Cog
from utils import checks
from utils.funcs import get_prefix, reaction_backoff, replace_mentions, FakeMessage
from utils.paginator import CannotPaginate

MODULES = (
	'Google',
	'Commands',
	'Moderation',
	'Info',
	'Utils',
	'Fun',
	'Chan',
	'Debug',
	'Stats',
	'Tags',
	'Logs',
	'Wc',
	'Changes',
	# 'Verification',
	'Nsfw',
	'Reminders',
	# 'JoinLeave',
	'Afk',
	'Raids',
	'Roles',
	# 'PlaceHolder',
)

# Disabled cogs
# 'Logging',
# 'FP',
# 'Markov'

# allowed_mention_chars = '!&123456789'


async def handle_filter_kwargs(kwargs, content, guild, state):
	# Stringify exceptions
	content = str(content)

	if kwargs.pop('replace_mentions', True):
		limit = kwargs.pop('replace_mentions_limit', None)
		content = await replace_mentions(state, guild, content, limit=limit)
		if limit is None or content.count("@") <= limit:
			content = str(content).replace("@", "@\u200b")

	if kwargs.pop('replace_everyone', True):
		content = content.replace('@everyone', '@\u200beveryone') \
			.replace('@here', '@\u200bhere')

	if kwargs.pop('zero_width', False):
		content = f"\u200b{content}"

	return content


class NotSoContext(commands.Context):
	def __init__(self, **attrs):
		self.piped = None
		super().__init__(**attrs)


	async def send(self, content=None, file=None, files=None, embed=None, **kwargs):
		if kwargs.pop('hastebin', False) and len(content) > 2000:
			url = await self.bot.funcs.hastebin(content)
			return await self.send(url)

		if isinstance(content, BytesIO):
			file = content
			content = None

		if file and isinstance(file, str) and not isfile(file):
			content = file
			file = None
		elif file is False:
			raise discord.InvalidArgument('\N{WARNING SIGN} `Image download failed/timed out.`')
		elif content is not None:
			content = await handle_filter_kwargs(
				kwargs, content,
				self.guild, self._state
			)

			# if "@" in content:
			# 	# fix 1
			# 	clean_content = content
			# 	for idx, char in enumerate(content):
			# 		if char == "@":
			# 			if idx > 0:
			# 				b = content[idx - 1]
			# 				if b == '<' and (content[idx + 1] in allowed_mention_chars):
			# 					continue
			# 			i = idx + 1
			# 			clean_content = content[:i] + '\u200b' + content[i:]

			# 	content = clean_content

				# # fix 2
				# special_chars = sum(1 for x in content if x not in ascii_letters)
				# # minimum is 300 combine @ + special char
				# if special_chars >= 250:
				# 	content = content.replace("@", "")

		filename = kwargs.pop('filename', None)
		if file or files:
			types = (BytesIO, str)
			if file and isinstance(file, types):
				file = discord.File(file, filename)
			elif files and all(isinstance(x, types) for x in files):
				files = [discord.File(_, f"{i}{filename}") for i, _ in enumerate(files, 1)]

		try:
			if self.piped:
				if file or files or embed:
					if embed and embed.image:
						self.cached.append(embed.image.proxy_url or embed.image.url)
					else:
						file = file or files[0]
						expire = self.cached[0]
						key = self.message.id
						if expire < 30:
							key += expire
						self.cached.append(await self.bot.funcs.store_cache(
							f"{key}{file.filename}", file.fp.read(), expire * 1000 # Seconds to ms
						))
						# Bypass ownership
						file._closer()
				if content:
					self.cached.append(content.encode())
				return
		#if its a non context call
		except AttributeError:
			pass

		#pylint: disable=E1003
		message = await super(self.__class__, self).send(
			content, file=file, files=files,
			embed=embed, **kwargs
		)

		if getattr(self, 'bot', False) and 'delete_after' not in kwargs \
			 and not isinstance(self.message, discord.Object):
			self.bot.command_messages[self.message.id][2].append(message.id)
		return message


	async def edit(self, content=None, **kwargs):
		if self.piped and content:
			return self.cached.append(content.encode())
		return await super().edit(content=content, **kwargs)


	async def delete(self, *args, error=True):
		try:
			if not error and not self.channel.permissions_for(self.me).manage_messages:
				return

			# Message IDs passed in
			if any(isinstance(x, int) for x in args):
				args = list(args)
				for idx, mid in enumerate(args):
					if isinstance(mid, int):
						args[idx] = FakeMessage(self, mid)

			self.bot.pruned_messages.extend(x.id for x in args)

			if len(args) > 1 and isinstance(self.channel, discord.TextChannel):
				return await self.channel.delete_messages(args)
			for m in args:
				await m.delete()
		except Exception as e:
			if error:
				raise e


	async def purge(self, *args, **kwargs):
		deleted = await self.channel.purge(*args, **kwargs)
		self.bot.pruned_messages.extend(x.id for x in deleted)
		return deleted


	async def add_reaction(self, message, reaction):
		c =  partial(message.add_reaction, reaction)
		await reaction_backoff(c)


	async def remove_reaction(self, message, reaction, user):
		c = partial(message.remove_reaction, reaction, user)
		await reaction_backoff(c)

discord.channel.TextChannel.send = NotSoContext.send

class Core(Cog):
	def __init__(self, bot):
		super().__init__(bot)

		# Globalization
		bot.process_commands = self.process_commands
		bot.send_message = self.send_message
		bot.on_error = self.on_error
		bot.load_modules = self.load_modules

		# Localization
		self.is_owner = bot.is_owner
		self.is_blacklisted = bot.funcs.is_blacklisted
		self._skip_check = bot._skip_check
		self.command_check = bot.funcs.command_check
		self.command_messages = bot.command_messages
		self.pruned_messages = bot.pruned_messages
		self.self_bot = bot.self_bot
		self.dev_mode = bot.dev_mode
		self.format_code = bot.funcs.format_code
		self.check_cooldown = bot.funcs.check_cooldown
		self.store_cache = bot.funcs.store_cache

		# Local
		self.piping_enabled = True
		self.pop = ';'
		self.no_typing = (
			'phone',
		)

		sentry_sdk.init(
			dsn=bot.funcs.dsn, release=self.bot.funcs.release
		)
		self.client_lock = asyncio.Lock(loop=bot.loop)


	#Startup

	async def load_modules(self):
		for cog in MODULES:
			self.bot.load_extension(f"mods.{cog}")


	@commands.Cog.listener()
	async def on_ws_connect(self, shard_id):
		print("WS CONNECTED", shard_id)

	@commands.Cog.listener()
	async def on_connect(self, shard_id):
		print("CONNECTED", shard_id)

	@commands.Cog.listener()
	async def on_disconnect(self, shard_id):
		print("DISCONNECTED", shard_id)

	@commands.Cog.listener()
	async def on_resuming(self, shard_id):
		print("RESUMING", shard_id)

	@commands.Cog.listener()
	async def on_resumed(self, shard_id):
		print("RESUMED", shard_id)

	@commands.Cog.listener()
	async def on_ready(self):
		if self.bot.self_bot:
			print('------\nSelf Bot\n{0}\n------'.format(self.bot.user))
		else:
			print('------\n{0}\nShard {1}/{2}{3}\n------'.format(
				self.bot.user, self.bot.shard_ids,
				self.bot.shard_count - 1,
				'\nDev Mode: Enabled' if self.bot.dev_mode else ''
			))

			await self.bot.change_presence(activity=discord.Game(name="."))

		# Override d.py's signal handler
		loop = self.bot.loop
		loop.add_signal_handler(signal.SIGINT, lambda: self.signal_override())
		loop.add_signal_handler(signal.SIGTERM, lambda: self.signal_override())

		# Prevent references to old guilds / etc
		self.bot.command_messages._purge()

	# TODO: add better interface to adding stop functions
	# SIGTERM HANDLER - DOCKER STOP
	async def _handle_stop(self):
		try:
			for cog in self.bot.cogs.values():
				if hasattr(cog, "handle_stop"):
					await cog.handle_stop()
		finally:
			self.bot.loop.stop()

	def signal_override(self):
		self.bot.loop.create_task(self._handle_stop())

	#Command Handling

	async def process_commands(self, message):
		self.bot.last_message = message.created_at
		# await self.bot.wait_until_ready()
		if message.author.bot:
			return
		elif (self.dev_mode or self.self_bot) and not await self.is_owner(message.author):
			return
		elif not self.self_bot and (message.author == self.bot.user or await self.is_blacklisted(message)):
			return
		ctx = await self.get_context(message)
		if ctx is None:
			return
		ctx, piped = ctx
		cmd = ctx.command.name
		prefix = ctx.prefix
		mentions = message.mentions[:]
		if await self.command_check(message, cmd):
			return
		if cmd not in self.no_typing and self.bot.http._global_over.is_set():
			try:
				await message.channel.trigger_typing()
			except:
				pass
		ctx.message.mentions = mentions
		self.command_messages[message.id] = (cmd, prefix, [], ctx.author.id)
		try:
			await self.invoke(ctx, piped)
		except:
			raise

	@commands.Cog.listener()
	async def on_message_edit(self, before, after):
		if before.content == after.content:
			return
		elif before.created_at < datetime.datetime.utcnow() - datetime.timedelta(minutes=5):
			return
		if after.id in self.command_messages:
			bot_msgs = self.command_messages[after.id][2]
			try:
				http = after._state.http
				cid = after.channel.id
				if len(bot_msgs) > 1:
					await http.delete_messages(cid, bot_msgs)
				else:
					await http.delete_message(cid, bot_msgs[0])
				self.pruned_messages.extend(bot_msgs)
			except:
				pass
		# after.member is downgraded to User for some reason..
		if isinstance(after.author, discord.User):
			after.author = before.author
		await self.process_commands(after)

	#Funcs


	#	'.retro aaa | test aaa ; magik ; jpeg'
	async def process_piping(self, split, author, prefix):
		piped = None
		for sp in split:
			sp = sp.strip().lstrip(prefix)
			fsp = sp.split(maxsplit=1)
			if not fsp:
				continue
			first = fsp[0]
			cmd = self.bot.all_commands.get(first, None)
			if cmd and cmd.module == 'mods.Fun':
				if piped is None:
					#max of 3 piped commands (excluding original invoker)
					piped = deque(maxlen=4) \
									if not await self.is_owner(author) \
									else []
				args = sp[len(first) + 1:]
				piped.append((f"{first} {args}", cmd))
		if piped and len(piped) == 1:
			piped = None
		return piped

	async def get_context(self, message, prefixes=None):
		prefixes = prefixes or await get_prefix(self.bot, message)
		for prefix in prefixes:
			message_regex = re.compile(rf"^({re.escape(prefix)})[\s]*(\w+)(.*)", re.I|re.X|re.S)
			match = message_regex.findall(message.content)
			if match:
				break
		if not match:
			return
		match = match[0]
		invoked_prefix = match[0].lower()
		message.content = f"{invoked_prefix}{match[1].lower()}{match[2]}"
		#piping operator
		pop = self.pop
		piped = pop in message.content
		if self.piping_enabled:
			if piped:
				#edge case for prefix being piping operator
				if invoked_prefix == pop:
					split = message.content.rsplit(pop, message.content.count(pop) - 1)
				else:
					split = message.content.split(pop)

				#modify message content to first command invoked
				if not split[-1].strip():
					piped = False
				else:
					piped = await self.process_piping(split, message.author, invoked_prefix)
					if piped:
						message.content = split[0]

		view = StringView(message.content)
		ctx = NotSoContext(prefix=None, view=view, bot=self.bot, message=message)
		view.skip_string(invoked_prefix)
		invoker = view.get_word()
		ctx.invoked_with = invoker
		ctx.prefix = invoked_prefix
		command = self.bot.all_commands.get(invoker)
		if command is None:
			return
		ctx.command = command
		if piped:
			ctx.piped = piped
			ctx.cached = []
		return ctx, piped


	async def invoke(self, ctx, piped):
		if piped and ctx.piped:
			not_owner = not await self.is_owner(ctx.author)
			if not_owner:
				await self.check_cooldown(1, ctx,
					"\N{NO ENTRY} **Cooldown** `Cannot pipe for another {:.2f} seconds.`", True
				)

			lp = len(ctx.piped)
			it = time()
			for idx, p in enumerate(ctx.piped):
				e = discord.Embed(title=p[0][:256])
				if idx != 0:
					# Re-init StringView
					view = StringView(f"{p[0]} {' '.join(filter(lambda x: isinstance(x, str), ctx.cached))}")
					# Clear the output cache for the next run
					ctx.cached.clear()
					ctx.view = view
					view.skip_string(""); view.get_word()
					ctx.command = p[1]
				else:
					if not ctx.channel.permissions_for(ctx.me).embed_links:
						raise CannotPaginate('Bot does not have `embed_links` permission for piping.')
					e.description = f"\N{HOURGLASS WITH FLOWING SAND} Piping {lp} commands"
					# Don't need NotSoContext.send, can't mention ping in embeds
					m = await super(ctx.__class__, ctx).send(embed=e)
					self.bot.command_messages[ctx.message.id][2].append(m.id)

				# Return on cooldown
				if ctx.cached:
					return await m.edit(content=ctx.cached[0].decode())

				is_last = (idx + 1) == lp
				t = time()
				# 5 min cache for last result, 10s + current index to circumvent discord cache
				ctx.cached.append(300 if is_last else 60 + idx)

				# Wait on ratelimit to prevent cooldown on cooldown messages
				try:
					await self.bot.invoke(ctx)
				except commands.CommandOnCooldown as e:
					if not_owner:
						ra = e.retry_after
						# Let the user know
						e.description = f"\N{TIMER CLOCK} Waiting {ra:.2f} seconds for cooldown."
						await m.edit(embed=e)

						# Sleep then bypass checks
						await asyncio.sleep(ra)
						await ctx.reinvoke()

				# Using embed as a progress "bar" through images
				e.timestamp = datetime.datetime.now()
				if is_last:
					e.set_footer(text="\N{HOLE} Piping took {:.01f}s".format(time() - it))
				else:
					e.set_footer(text=f"\N{HOLE} Piping in progress: {idx + 1}/{lp}")

				# Set embed
				for c in ctx.cached[:3]:
					if isinstance(c, int):
						continue
					# Differentiate between imis cache and text content
					if isinstance(c, str):
						e.set_image(url=c)
					else:
						e.description = c.decode()

				# Don't update the embed too fast
				if (time() - t) < 1:
					await asyncio.sleep(1.5)
				# Edit with new results or create message and add to cmessages
				await m.edit(embed=e)
		else:
			await self.bot.invoke(ctx)

	async def send_message(self, channel, content=None, embed=None, **kwargs):
		if content:
			content = await handle_filter_kwargs(
				kwargs, content,
				None, self.bot._connection
			)
		if embed:
			embed = embed.to_dict()
		await self.bot.http.send_message(channel.id, content, embed=embed)
		# channel = self.get_channel(data.get('channel_id'))
		# return channel._state.create_message(channel=channel, data=data)

	#Events

	@commands.Cog.listener()
	async def on_error(self, event, *args, **kwargs): #pylint: disable=W0613
		async with self.client_lock:
			with sentry_sdk.push_scope() as scope:
				scope.set_tag("shard", self.bot.get_id())

				sentry_sdk.capture_exception()


	@commands.Cog.listener()
	async def on_command_error(self, ctx, e):
		x = None
		try:
			se = str(e)
			ec = e.__cause__
			if hasattr(ctx.command, 'on_error') and ctx.command.cog_name in se:
				return
			if isinstance(e, commands.CommandOnCooldown) and not ctx.piped:
				if await self.bot.is_owner(ctx.author):
					return await ctx.reinvoke()
				err = "\N{NO ENTRY} **Cooldown** `Cannot use again for another {:.2f} seconds.`".format(e.retry_after)
				x = await self.check_cooldown(0, ctx, err)
			elif isinstance(e, commands.MissingRequiredArgument):
				x = await self.bot.command_help(ctx)
				ctx.command.reset_cooldown(ctx)
			elif isinstance(e, commands.BadArgument):
				x = await ctx.send(f"\N{WARNING SIGN} `{se}`")
				ctx.command.reset_cooldown(ctx)
			elif isinstance(ec, discord.InvalidArgument):
				x = await ctx.send(ec)
			elif isinstance(ec, CannotPaginate):
				x = await ctx.send(f"\N{NO ENTRY} {se}")
			elif isinstance(e, checks.No_Perms):
				x = await ctx.send("\N{NO ENTRY} `No Permission`")
			elif isinstance(e, commands.NotOwner):
				x = await ctx.send("\N{NO ENTRY} `Bot Owner Only`")
			elif isinstance(e, checks.No_Mod):
				x = await ctx.send("\N{NO ENTRY} `Moderator or Above Only`")
			elif isinstance(e, checks.No_Admin):
				x = await ctx.send("\N{NO ENTRY} `Administrator Only`")
			elif isinstance(e, checks.No_Role):
				x = await ctx.send("\N{NO ENTRY} `No Custom Role or Specific Permission`")
			elif isinstance(e, checks.No_BotPerms):
				x = await ctx.send(f"\N{NO ENTRY} This command requires the bot to have `{se}` permission(s).")
			elif isinstance(e, checks.Nsfw):
				x = await ctx.send("\N{NO ONE UNDER EIGHTEEN SYMBOL} `NSFW command; requires channel marked as NSFW in its settings!`")
			elif isinstance(e, checks.No_DevServer):
				x = await ctx.send("\N{NO ENTRY} Command can only be used on `NotSoServer`.")
			elif isinstance(e, checks.No_Ids):
				x = await ctx.send(f"\N{NO ENTRY} Command can only be used by User IDs: `{se}`.")
			elif isinstance(e, commands.CheckFailure):
				x = await ctx.send("\N{WARNING SIGN} **Command check failed**\nCauses:\n `1.` Bot is missing `Administrator/Manage_roles` permission.\n `2.` You do not have proper permissions to run the command.\n `3.` The command is not to be used in PM's.")
				ctx.command.reset_cooldown(ctx)
			elif isinstance(ec, discord.HTTPException):
				if "Unknown Message" in str(ec):
					return
				x = await ctx.send(f"\N{WARNING SIGN} **Discord HTTPException**, *usually it is*: sending a file (> 8 mb)/message failed.\n{self.format_code(e)}")
			elif isinstance(ec, discord.Forbidden):
				x = await ctx.send('\N{WARNING SIGN} **Discord Forbidden Error**, the bot is missing guild/role permission to run the command (i.e. manage_files to upload).')
			elif isinstance(ec, RuntimeError):
				x = await ctx.send('\N{WARNING SIGN} **RuntimeError**, command failed (bot under heavy load).')
			elif isinstance(ec, FileNotFoundError):
				x = await ctx.send('\N{WARNING SIGN} Command could **not find** image file to process... Most likely due to **invalid user input** or a bug.')
			elif isinstance(ec, OSError) or (isinstance(ec, AttributeError) and str(ec) == "'bool' object has no attribute 'read'") or (isinstance(ec, TypeError) and str(ec) == "file must be a readable file object, but the given object does not have read() method"):
				x = await ctx.send('\N{WARNING SIGN} **Command download function failed...**')
			elif isinstance(ec, AssertionError):
				x = await ctx.send(f"\N{WARNING SIGN} `{str(ec)}`")
			elif isinstance(e, commands.CommandInvokeError):
				try:
					raise e.original
				except:
					async with self.client_lock:
						with sentry_sdk.push_scope() as scope:
							scope.set_tag("shard", self.bot.get_id())
							scope.set_tag("command", ctx.command.qualified_name)

							scope.set_extra("message", ctx.message.content)
							scope.set_extra("clean_message", ctx.message.clean_content)
							scope.set_extra("server", "{0.name} <{0.id}>".format(ctx.guild) \
														 						 if ctx.guild else 'Private Message')
							scope.set_extra("author", "{0.name} <{0.id}>".format(ctx.author))
							if ctx.piped:
								scope.set_extra("piped", str(ctx.piped))
								scope.set_extra("piped_cache", str(ctx.cached))

							sentry_sdk.capture_exception()
			elif isinstance(e, commands.NoPrivateMessage):
				x = await ctx.send('\N{WARNING SIGN} `Command disabled in Private Messaging.`')
		except (discord.Forbidden, discord.HTTPException):
			return
		if x:
			self.bot.command_messages[ctx.message.id][2].append(x.id)


	@commands.Cog.listener()
	async def on_guild_remove(self, guild):
		clause = f" guild={guild.id}"
		sql = f"DELETE FROM `prefix_channel` WHERE" + clause
		await self.cursor.execute(sql)
		sql = "DELETE FROM `prefix` WHERE" + clause
		await self.cursor.execute(sql)


def setup(bot):
	bot.add_cog(Core(bot))
