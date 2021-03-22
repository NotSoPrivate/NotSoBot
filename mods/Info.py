import time
from datetime import datetime
from urllib.parse import quote
from itertools import groupby

import aiosteam
import ujson as json
import wolframalpha

import discord
from discord.ext import commands

from mods.cog import Cog
from utils.paginator import CannotPaginate, HelpPaginator, Pages


class PaginatedHelpCommand(commands.HelpCommand):
	def __init__(self):
		super().__init__(command_attrs={
			'cooldown': commands.Cooldown(1, 3.0, commands.BucketType.member),
			'help': 'Shows help about the bot, a command, or a category'
		})

	async def send_website(self, ctx=None):
		ctx = ctx or self.context
		await ctx.send(f"{ctx.author.mention}: https://mods.nyc/help", replace_mentions=False)

	async def on_help_command_error(self, ctx, error):
		await self.send_website(ctx)

	def get_command_signature(self, command):
		parent = command.full_parent_name
		if len(command.aliases) > 0:
			aliases = '|'.join(command.aliases)
			fmt = f'[{command.name}|{aliases}]'
			if parent:
				fmt = f'{parent} {fmt}'
			alias = fmt
		else:
			alias = command.name if not parent else f'{parent} {command.name}'
		return f'{alias} {command.signature}'

	async def send_bot_help(self, mapping):
		await self.send_website()
		# def key(c):
		# 	return c.cog_name or '\u200bNo Category'

		# bot = self.context.bot
		# entries = await self.filter_commands(bot.commands, sort=True, key=key)
		# nested_pages = []
		# per_page = 9
		# total = 0

		# for cog, commands in groupby(entries, key=key):
		# 	commands = sorted(commands, key=lambda c: c.name)
		# 	if len(commands) == 0:
		# 		continue

		# 	total += len(commands)
		# 	actual_cog = bot.get_cog(cog)
		# 	# get the description if it exists (and the cog is valid) or return Empty embed.
		# 	description = (actual_cog and actual_cog.description) or discord.Embed.Empty
		# 	nested_pages.extend((cog, description, commands[i:i + per_page]) for i in range(0, len(commands), per_page))

		# # a value of 1 forces the pagination session
		# pages = HelpPaginator(self, self.context, nested_pages, per_page=1)

		# # swap the get_page implementation to work with our nested pages.
		# pages.get_page = pages.get_bot_page
		# pages.total = total
		# await pages.paginate()

	async def send_cog_help(self, cog):
		entries = await self.filter_commands(cog.get_commands(), sort=True)
		pages = HelpPaginator(self, self.context, entries)
		pages.title = f'{cog.qualified_name} Commands'
		pages.description = cog.description

		await pages.paginate()

	def common_command_formatting(self, page_or_embed, command):
		page_or_embed.title = self.get_command_signature(command)
		if command.description:
			page_or_embed.description = f'{command.description}\n\n{command.help}'
		else:
			page_or_embed.description = command.help or 'No help found...'

	async def send_command_help(self, command):
		# No pagination necessary for a single command.
		embed = discord.Embed(colour=discord.Colour.blurple())
		self.common_command_formatting(embed, command)
		await self.context.send(embed=embed)

	async def send_group_help(self, group):
		subcommands = group.commands
		if len(subcommands) == 0:
			return await self.send_command_help(group)

		entries = await self.filter_commands(subcommands, sort=True)
		pages = HelpPaginator(self, self.context, entries)
		self.common_command_formatting(pages, group)

		await pages.paginate()


class Info(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.discord_path = bot.path.discord
		self.files_path = bot.path.files
		self.truncate = bot.funcs.truncate
		self.get_json = bot.get_json
		self.get_default_channel = bot.funcs.get_default_channel
		self.get_role_color = bot.funcs.get_role_color
		self.f_api = bot.funcs.f_api
		self.wa = wolframalpha.Client('X9HA7A-8Y5E82WTAG')
		self.diff = "```diff\n{0}\n```"
		self.cool = "```xl\n{0}\n```"
		aiosteam.set_key('82CA186775ADB0B167FE935AB4F61633', '48ce0be1b35b47ac606feeb4')
		self.persona_map = {
			0: 'Offline',
			1: 'Online',
			2: 'Busy',
			3: 'Away',
			4: 'Snooze',
			5: 'Looking to trade',
			6: 'Looking to play'
		}
		self.perspective_attrs = (
			"TOXICITY",
			"TOXICITY_FAST",
			"ATTACK_ON_AUTHOR",
			"ATTACK_ON_COMMENTER",
			"INCOHERENT",
			"INFLAMMATORY",
			"OBSCENE",
			"OFF_TOPIC",
			"UNSUBSTANTIAL",
			"LIKELY_TO_REJECT"
		)

		self.vanity_invite = None

		# help command stuff
		bot.old_help_command = bot.help_command
		bot.help_command = PaginatedHelpCommand()
		bot.help_command.cog = self

	def cog_unload(self):
		self.bot.loop.create_task(self.wa.session.close())
		self.bot.help_command = self.bot.old_help_command

	@commands.command(aliases=['guild'])
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def server(self, ctx, *, guild:discord.Guild=None):
		if not guild:
			guild = ctx.guild
		e = discord.Embed()
		e.title = f'\N{DESKTOP COMPUTER} {guild.name}'
		e.color = discord.Color.blue()
		gi = guild.icon_url
		if gi:
			e.set_thumbnail(url=gi)
		msg = "\N{SQUARED ID}: `{0}`\n".format(guild.id)
		msg += "\N{BUST IN SILHOUETTE} **Owner**: <@{0}>\n".format(guild.owner_id)
		msg += "\N{WORLD MAP} **Region**: __{0}__\n".format(str(guild.region))
		msg += "\N{SPIRAL CALENDAR PAD} **Created**: `{0}`\n".format(str(guild.created_at.strftime('%m/%d/%Y %H:%M:%S')))
		# online = sum(1 for member in guild.members if member.status in (discord.Status.online, discord.Status.idle, discord.Status.invisible))
		# idle = sum(1 for member in guild.members if member.status == discord.Status.idle)
		# offline = guild.member_count - online - idle
		msg += "\N{BUSTS IN SILHOUETTE} **Total Users**: **{0}**\n".format(guild.member_count)
		if guild.verification_level:
			msg += "\N{HEAVY EXCLAMATION MARK SYMBOL} **Verification Level**: **{0}**\n".format(str(guild.verification_level).upper())
		msg += "\N{SPEECH BALLOON} **Default Channel**: {0}\n".format(self.get_default_channel(ctx.author, guild).mention)
		if ctx.guild.afk_channel:
			msg += "\N{TELEPHONE RECEIVER} **AFK Channel**: {0}\n".format(guild.afk_channel.mention)
			msg += "\N{KEYBOARD} **AFK Timeout**: {0} minutes\n".format(int(guild.afk_timeout) / 60)
		voice = sum(1 for channel in guild.channels if isinstance(channel, discord.VoiceChannel))
		text = len(guild.channels) - voice
		msg += "\N{BLACK RIGHT-POINTING TRIANGLE} **Channels**: `{0}` Text | `{1}` Voice | **{2}** Total\n".format(text, voice, str(len(guild.channels)))
		msg += "\N{BLACK RIGHT-POINTING TRIANGLE} **Roles**: `{0}`\n".format(str(len(guild.roles)))
		content = None
		emojis = await guild.fetch_emojis()
		if emojis:
			emote_msg = ''.join([str(e) for e in emojis])
			ebase = '\N{BLACK RIGHT-POINTING TRIANGLE} **Emojis**: '
			if len(emote_msg)+len(msg) >= 2048:
				if len(emote_msg) >= 1024:
					content = (ebase+emote_msg)[:2000]
				else:
					e.add_field(name=ebase, value=emote_msg)
			else:
				msg += ebase+emote_msg
		e.description = msg
		await ctx.send(content, embed=e)

	# D:
	@commands.command(aliases=['userinfo', 'user'])
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def info(self, ctx, *, user:discord.User=None):
		"""Returns inputed users info."""
		if user is None:
			user = ctx.author
		guild = ctx.guild
		check = isinstance(user, discord.Member)
		e = discord.Embed()
		e.title = f'\N{BUST IN SILHOUETTE} {user}'
		e.set_thumbnail(url=user.avatar_url or user.default_avatar_url)
		e.color = discord.Color.blue() if not check else self.get_role_color(user)
		e.description = """{0}\N{SQUARED ID}: `{1}`
\N{ROBOT FACE} **Bot**: {2}
\N{INBOX TRAY} **Guild Join Date**: __{3}__
\N{GLOBE WITH MERIDIANS} **Discord Join Date**: __{4}__
{5}{6}
\N{SHIELD} **Roles**: {7} - `{8}`
""".format('\N{NAME BADGE} **Nickname**: {0}\n'.format(user.nick) if check and user.nick else '', \
					user.id, 'Yes' if user.bot else 'No', \
					user.joined_at.strftime('%m/%d/%Y %H:%M:%S') if check and user.joined_at != None else 'N/A', \
					user.created_at.strftime('%m/%d/%Y %H:%M:%S'), \
					'\n:joystick: Playing: \"{0}\"'.format(user.activity.name or '') if check and user.activity else '', \
					'\n:microphone2: Voice Channel: {0}'.format(user.voice.channel.name) if check and user.voice else '', \
					len(user.roles) if check else 1, ', '.join([role.name for role in user.roles]) if check else '@everyone')
		await ctx.send(embed=e)

	@commands.command()
	@commands.is_owner()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def seenon(self, ctx, *, user:discord.User=None):
		if user is None:
			user = ctx.author
		elif not await self.bot.is_owner(ctx.author) \
		and (user == self.bot.user or await self.bot.is_owner(user)):
			return await ctx.send('no')
		resp = await self.bot.rpc.seen_on(
			ctx.message.id,
			shards=True,
			guild=ctx.guild.id if ctx.guild else None,
			user=user.id
		)
		seen_on = list(resp)
		try:
			p = Pages(ctx, entries=seen_on, per_page=30,
				extra_info='# at the end of each name refers to the shard.'
			)
			p.embed.title = 'Guilds Seen On'
			if self.bot._connection.guild_subscriptions is False:
				p.embed.description = "Member cache is disabled," \
					"this will only show if they've been added to the cache."
			p.embed.color = 0x738bd7
			p.embed.set_author(name=user.display_name, icon_url=user.avatar_url or user.default_avatar_url)
			await p.paginate()
		except CannotPaginate:
			joined = ', '.join(seen_on)
			if len(joined) >= 2000:
				return await ctx.send(
					'\N{NO ENTRY} `Too many seen on guilds for non-embed response, please allow me to post embeds!`'
				)
			await ctx.send(f"**Guilds Seen On for __{user}__**\n`{joined}`")

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def invite(self, ctx):
		"""returns invite link for bot"""
		if self.vanity_invite is None:
			_id = self.bot.guild_id
			g = self.bot.get_guild(_id) or await self.bot.fetch_guild(_id)
			try:
				self.vanity_invite = str(await g.vanity_invite())
			except discord.HTTPException:
				self.vanity_invite = "https://discord.gg/9Ukuw9V"
		msg = self.diff.format('+ Invite me to your guild with this url')
		msg += '<https://discordapp.com/oauth2/authorize?client_id=439205512425504771&scope=bot&permissions=8&response_type=code&redirect_uri=https://mods.nyc/help>'
		msg += self.diff.format("- Uncheck Administrator permission if you do not need Admin/Moderation commands.\n+ + +\n! Join NotSoServer for any questions or help with the bot!")
		msg += self.vanity_invite
		await ctx.send(msg)

	@commands.command()
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def avatar(self, ctx, *, user:discord.User=None):
		"""Returns the input users avatar."""
		if user is None:
			user = ctx.author
		await ctx.send(f"`{user}`'s avatar is: {user.avatar_url_as(static_format='png')}")

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def uptime(self, ctx):
		"""How long have I been up/online?"""
		seconds = time.time() - self.bot.start_time
		m, s = divmod(seconds, 60)
		h, m = divmod(m, 60)
		d, h = divmod(h, 24)
		w, d = divmod(d, 7)
		if s != 0:
			msg = '**{0}** seconds{1}.'.format(int(s), ' :frowning:' if m == 0 else '')
		if m != 0:
			e = ' :slight_frown:.' if h == 0 else '.'
			msg = ' : **{0}** minutes : '.format(int(m)) + msg.replace('.', '') + e
		if h != 0:
			e = ' :slight_smile:.' if d == 0 else '.'
			msg = ' : **{0}** hours'.format(int(h)) + msg.replace('.', '') + e
		if d != 0:
			e = ' :smiley:.' if w == 0 else '.'
			msg = ' : **{0}** days'.format(int(d)) + msg.replace('.', '').replace(':slight_smile:', '') + e
		if w != 0:
			msg = ' : **{0}** weeks'.format(int(w)) + msg.replace('.', '') + ' :joy: :joy: :joy: :joy: :joy: :joy: :joy: :joy: :joy: :joy:.'
		if m == 0:
			msg = ' '+msg
		else:
			msg = msg[2:]
		await ctx.send(f":clock4: Online for{msg}")

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def steam(self, ctx, *, txt:str):
		try:
			suser = await aiosteam.get_user(txt)
			assert suser
		except:
			return await ctx.send('\N{WARNING SIGN} `Cannot find steam user (input a SteamID/64/Username).`')
		level = await aiosteam.get_user_level(txt)
		nl = '\n'
		msg = f"""
Username: {suser.name}{f"{nl}Real Name: {suser.realName}" if suser.realName else ''}{f"{nl}Level: {level}" if level is not None else ''}
Persona: {self.persona_map[suser.personaState]}
URL: {suser.url}
Avatar: {suser.avatarFull}
Country: {suser.country}{f"{nl}State: {suser.statecode}" if suser.statecode else ''}
Last Log-off: {datetime.fromtimestamp(suser.lastLogoff).strftime('%m/%d/%Y %H:%M:%S') if suser.lastLogoff else 'Private'}
Created: {datetime.fromtimestamp(suser.created).strftime('%m/%d/%Y %H:%M:%S') if suser.created else 'Private'}
"""
		await ctx.send(self.cool.format(msg))

	# @commands.command()
	# @commands.cooldown(2, 5, commands.BucketType.guild)
	# async def steam(self, ctx, stem:str):
	# 	"""Returns Steam information of inputed SteamID/Custom URL/Etc"""
	# 	steamId = None
	# 	steamProfile = None
	# 	if steamId is None: 
	# 		steamId = SteamId.fromSteamId("{0}".format(stem))
	# 	if steamId is None: 
	# 		steamId = SteamId.fromSteamId3(stem)
	# 	if steamId is None: 
	# 		steamId = SteamId.fromSteamId64(stem)
	# 	if steamId is None: 
	# 		steamId = SteamId.fromProfileUrl(stem)
	# 	if steamId is None: 
	# 		steamProfile = SteamProfile.fromCustomProfileUrl(stem)
	# 		if steamProfile is None:
	# 			await ctx.send("bad steam id")
	# 			return
	# 		steamId = steamProfile.steamId
	# 	else:
	# 		steamProfile = SteamProfile.fromSteamId(steamId)
	# 	msg = ""
	# 	if steamProfile is not None and \
	# 		steamProfile.displayName is not None:
	# 			msg += "Username: " + steamProfile.displayName + "\n"
	# 	steam_user = steamapi.user.SteamUser(steamId.steamId64)
	# 	if steam_user.state == 0:
	# 		msg += "Status: Offline\n"
	# 	elif steam_user.state == 1:
	# 		msg += "Status: Online\n"
	# 	elif steam_user.state == 2:
	# 		msg += "Status: Busy\n"
	# 	elif steam_user.state == 3:
	# 		msg += "Status: Away\n"
	# 	elif steam_user.state == 4:
	# 		msg += "Status: Snooze\n"
	# 	elif steam_user.state == 5:
	# 		msg += "Status: Looking to Trade\n"
	# 	elif steam_user.state == 6:
	# 		msg += "Status: Looking to Play\n"
	# 	msg += "Avatar: \"{0}\"\n".format(str(steam_user.avatar_full))
	# 	if steam_user.level != None:
	# 		msg += "Level: {0}\n".format(str(steam_user.level))
	# 	if steam_user.currently_playing != None:
	# 		msg += "Currently Playing: {0}\n".format(str(steam_user.currently_playing))
	# 	elif steam_user.recently_played != []:
	# 		msg += "Recently Played: {0}\n".format(str(steam_user.recently_played).replace("<SteamApp ", "").replace(">", "").replace("[", "").replace("]", ""))
	# 	msg += "Created: {0}\n".format(str(steam_user.time_created))
	# 	msg += "Steam ID: " + steamId.steamId + "\n"
	# 	msg += "Steam ID 64: " + str(steamId.steamId64) + "\n"
	# 	msg += "Permanent Link: \"" + steamId.profileUrl + "\"\n"
	# 	if steamProfile != None and \
	# 		steamProfile.customProfileUrl != None:
	# 			msg += "Link: \"" + steamProfile.customProfileUrl + "\"\n"
	# 	msg = msg.replace("'", "′")
	# 	await ctx.send(self.cool.format(msg))

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def cinfo(self, ctx):
		"""Return Channel Information"""
		msg = "Channel Name: {0}\n".format(ctx.channel.name)
		msg += "Channel ID: {0}\n".format(ctx.channel.id)
		msg += "Channel Created: {0}\n".format(ctx.channel.created_at)
		await ctx.send(self.cool.format(msg))

	@commands.command()
	async def botc(self, ctx, *, text:str):
		txt = text.split()
		msg = "https://github.com/NotSoSuper/notsosuper_bot/search?q={0}".format("+".join(txt))
		await ctx.send(msg)

	@commands.command()
	async def statsmin(self, ctx):
		q = await self.cursor.execute('SELECT * FROM `stats`')
		guilds = await q.fetchall()
		q = await self.cursor.execute('SELECT COUNT(`command`) FROM `command_logs`')
		cmds = (await q.fetchone())['COUNT(`command`)']
		await ctx.send('**{0}** guilds\n**{1}** commands'.format(sum(x['guilds'] for x in guilds), cmds))

	@commands.command(aliases=['sof'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def stackoverflow(self, ctx, *, text:str):
		try:
			api = 'https://api.stackexchange.com/2.2/search?order=desc&sort=votes&site=stackoverflow&intitle={0}'.format(quote(text))
			r = await self.get_json(api)
			q_c = len(r['items'])
			if q_c == 0:
				api = 'https://api.stackexchange.com/2.2/similar?order=desc&sort=votes&site=stackoverflow&title={0}'.format(quote(text))
				r = await self.get_json(api)
				q_c = len(r['items'])
			if q_c == 0:
				api = 'https://api.stackexchange.com/2.2/search/excerpts?order=desc&sort=votes&site=stackoverflow&q={0}'.format(quote(text))
				r = await self.get_json(api)
				q_c = len(r['items'])
			if q_c == 0:
				api = 'https://api.stackexchange.com/2.2/search/advanced?order=desc&sort=votes&site=stackoverflow&q={0}'.format(quote(text))
				r = await self.get_json(api)
				q_c = len(r['items'])
			if q_c == 0:
				return await ctx.send("\N{WARNING SIGN} `No results found on` <https://stackoverflow.com>")
			if q_c > 5:
				msg = "**First 5 Results For: `{0}`**\n".format(text)
			else:
				msg = "**First {0} Results For: `{1}`**\n".format(str(q_c), text)
			count = 0
			for s in r['items']:
				if q_c > 5:
					if count == 5:
						break
				else:
					if count == q_c:
						break
				epoch = int(s['creation_date'])
				date = str(datetime.fromtimestamp(epoch).strftime('%m-%d-%Y'))
				msg += "```xl\nTitle: {0}\nLink: {1}\nCreation Date: {2}\nScore: {3}\nViews: {4}\nIs-Answered: {5}\nAnswer Count: {6}```".format(s['title'], s['link'].replace("http://", "").replace("https://", "").replace("www.", ""), date, s['score'], s['view_count'], s['is_answered'], s['answer_count'])
				count += 1
			await ctx.send(msg)
		except:
			await ctx.send("\N{WARNING SIGN} `No results found on` <https://stackoverflow.com>")
			raise

	@commands.command(aliases=['wa', 'wolfram'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def wolframalpha(self, ctx, *, q:str):
		try:
			result = await self.wa.query(q, proxy=self.bot.funcs.proxy)
		except:
			return await ctx.send('\N{WARNING SIGN} Wolfram Alpha API Failed.')
		if result is None or result['@success'] == 'false':
			return await ctx.send('\N{WARNING SIGN} `No results found on` <https://wolframalpha.com>')
		imgs = []
		prev = False
		try:
			pods = list(result.pods)
		except AttributeError:
			return await ctx.send('\N{NO ENTRY} Standard computation time exceeded...')
		load = {}
		for pod in pods:
			if 'subpod' not in pod:
				continue
			subs = pod['subpod']
			if isinstance(subs, dict):
				subs = (subs,)
			for sub in subs:
				txt = sub['plaintext']
				if txt == prev:
					continue
				elif txt:
					load[pod['@title']] = txt
				if 'img' in sub:
					imgs.append(sub['img']['@src'])
				if txt != None:
					prev = txt
		imgs.reverse()
		try:
			p = Pages(ctx, entries=imgs, images=True, minimal=True)
			e = p.embed
			e.title = 'Wolfram|Alpha Result'
			for x in load:
				e.add_field(name=x, value=load[x])
			e.set_thumbnail(url='https://cdn.discordapp.com/attachments/178313653177548800/287641775823126538/Pd8NO4lgMW1gsSrlv_zqoFq18mXrVz0AE-Nrxn5sijtp7AacJywTWoM_1kaJeorJKOhVw300.png')
			e.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url)
			e.color = discord.Colour(int("FF4C4C", 16))
			await p.paginate()
		except CannotPaginate:
			msg = '\n'.join([f'**{x}**: `{load[x]}`' for x in load])
			#usually cause bot doesnt have embed perms but add images anyways ;-;
			msg += '\n' + '\n'.join(imgs[:3])
			if len(msg) >= 2000:
				await ctx.send('\N{WARNING SIGN} Results too long...')
			else:
				await ctx.send(msg)

	@commands.command()
	@commands.cooldown(1, 15, commands.BucketType.guild)
	async def botlist(self, ctx, page:int=1):
		load = await self.get_json('https://www.carbonitex.net/discord/api/listedbots', timeout=7)
		if not load:
			return await ctx.send('\N{WARNING SIGN} `Carbonitex API Failed.`')
		bots = sorted(load, reverse=True, key=lambda x: int(x['servercount']))
		entries = []
		for bot in bots:
			if bot['compliant']:
				entries.append(f"**{bot['name']}** - {bot['servercount']} (Compliant)")
			else:
				entries.append(f"**{bot['name']}** - {bot['servercount']}")
		try:
			p = Pages(ctx, entries=entries, per_page=10, page=page)
			p.embed.title = 'Carbonitex Bot List'
			p.embed.color = 0x738bd7
			await p.paginate()
		except CannotPaginate:
			await ctx.send('give me embed perms smelly')

	@commands.command(aliases=['sp'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def steamplaying(self, ctx, *, game:str):
		result = await self.f_api('steamplaying', text=game, raw=True)
		await ctx.send(result)

	async def perspective_api(self, ctx, text, attrs):
		api = 'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze?key=AIzaSyC1isdXudsZ4O-0YULhxif2sNvkSv9PbZ0'
		payload = {
			"comment": {
				"text": text,
				"type": "PLAIN_TEXT"
			},
			"requestedAttributes": {x: {} for x in attrs},
			"languages": ["en"],
			"doNotStore": True
		}
		load = await self.get_json(api, data=json.dumps(payload), headers={'content-type': 'application/json'})
		if not load:
			await ctx.send('\N{WARNING SIGN} `Google perspective API error.`')
			return False
		elif "error" in load:
			await ctx.send(load["error"]["message"])
			return False
		return load

	@commands.command(aliases=['toe', 'analyze', 'perspective'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def tone(self, ctx, *, text:commands.clean_content):
		"""Run Google Perspective on text"""
		load = await self.perspective_api(ctx, text, self.perspective_attrs)
		if load is False:
			return
		e = discord.Embed()
		e.description = f"`{text}`"

		scores = load['attributeScores']
		scores = {s: scores[s]['summaryScore']['value'] for s in scores}
		for score, value in scores.items():
			value = f"{round(value * 100, 1)}%"
			e.add_field(name=score, value=value, inline=True)

		avg = (scores['TOXICITY'] + scores['OBSCENE']) / 2
		r = int(255 * avg)
		g = int(255 * (1 - avg))
		if r > g:
			b = 71
		else:
			b = 129
		e.color = r << 16 | g << 8 | b

		icon = 'https://cdn.discordapp.com/app-icons/324663951704981505/77cd059ce8a8c7a877cf2bf89ccc1b52.jpg'
		e.timestamp = ctx.message.created_at
		e.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url)
		e.set_footer(text='Powered by Google Perspective', icon_url=icon)
		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(Info(bot))
