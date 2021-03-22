import hashlib
import re
import time
import unicodedata
from urllib.parse import quote

import discord
from discord.ext import commands

import ujson as json
from mods.cog import Cog
from utils import checks


class Utils(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.bytes_download = bot.bytes_download
		self.get_text = bot.get_text
		self.f_api = bot.funcs.f_api
		self.generic_api = bot.funcs.generic_api
		self.post_data = bot.post_data
		with open(bot.funcs.discord_path('utils/pings.txt')) as f:
			self.ping_responses = f.read().split('\n')
		import random
		self.ping_count = random.randint(0, len(self.ping_responses)-1)
		self.bad_status = re.compile(r'(https?...)?discord(\.)?(gg|me|app\.com)(\/invite)?(\/|\\).', re.I|re.S)
		self.format_code = bot.funcs.format_code
		self.perspective_api = bot.get_cog('Info').perspective_api


	@commands.command()
	@commands.cooldown(2, 20)
	@commands.is_owner()
	@checks.DevServer()
	async def status(self, ctx, *, status:str):
		"""changes bots status"""
		r = await self.bot.rpc.send_command('status', ctx.message.id, status=status)
		await ctx.send(f"ok, status changed to `{status}` on **{r}** shards.")

	@commands.command()
	@commands.is_owner()
	async def say(self, ctx, *, text:str):
		"""have me say something (owner only cuz exploits)???"""
		await ctx.send(text, replace_mentions=False, replace_everyone=False)

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.user)
	async def ping(self, ctx, ip:str=None):
		"""Ping the bot server."""
		ptime = time.time()
		x = await ctx.send("ok, pinging.")
		msg = None
		if ip:
			msg = await self.bot.run_process(
				["ping",
					"-c", "4",
					ip.replace('https://', '').replace('http://', '').replace('www.', '')
				], True
			)
			if msg:
				msg = self.format_code(msg, 'xl')
		if not msg:
			if self.ping_count >= len(self.ping_responses):
				self.ping_count = 0
			kek = self.ping_responses[self.ping_count]
			self.ping_count += 1
			ping = time.time() - ptime
			msg = "ok, it took `{0}ms` to ping **{1}**{2}".format(
				round(ping * 1000), kek.replace('[nl]', '\n'),
				'\nlook how slow python is.' if ping > 1 else '.'
			)
		try:
			await x.edit(content=msg)
		except:
			#rip message
			pass

	@commands.command()
	@commands.cooldown(1, 15, commands.BucketType.guild)
	async def gist(self, ctx, *, arg):
		payload = {
			'name': 'NotSoBot - By: {0}.'.format(ctx.author),
			'text': arg,
			'private': '1',
			'expire': '0'
		}
		url = await self.post_data('https://spit.mixtape.moe/api/create', payload, text=True)
		await ctx.send('Uploaded to paste, URL: <https://spit.mixtape.moe{0}>'.format(url))

	@commands.command()
	@commands.is_owner()
	async def setavatar(self, ctx, url:str):
		"""Changes the bots avatar.\nOwner only ofc."""
		b = await self.bytes_download(url)
		await self.bot.user.edit(avatar=b.read())
		await self.bot.send(file=b, content="Avatar has been changed to:")

	@commands.command()
	@commands.is_owner()
	async def setname(self, ctx, *, name:str):
		"""Changes the bots name.\nOwner only ofc."""
		await self.bot.user.edit(username=name)
		await ctx.send("ok, username changed to `{0}`".format(name))

	async def do_sed(self, message, text=None):
		try:
			if not message.channel:
				return
			match = None
			found = False
			text = message.content if not text else text
			match = text.split('/')
			if match[0] != "s" and match[0] != "sed":
				if not self.bot.self_bot and match[0] != 're':
					return
			if len(match) != 1:
				text_one = match[1]
			else:
				return await message.channel.send("Error: Invalid Syntax\n`s/text to find (you are missing this)/text to replace with/`")
			if len(match) >= 3:
				text_two = match[2]
			else:
				return await message.channel.send("Error: Invalid Syntax\n`s/text to find/text to replace with (you are missing this)/`")
			async for m in message.channel.history(limit=50, before=message):
				if self.bot.self_bot and not await self.bot.is_owner(m.author):
					continue
				kwargs = {'content': m.clean_content or None, 'text_one': text_one, 'raw': True}
				if not found and not m.content.startswith(('s/', 'sed/')) \
					 and ((await self.generic_api('sed', check=True, **kwargs)) == '1'):
					found = True
					x = await self.generic_api('sed', text_two=text_two, **kwargs)
					if self.bot.self_bot:
						await message.delete()
						return await m.edit(content=x)
					msg = f"{m.author.name}: {x}"
					break
			if found:
				await message.channel.send(msg[:2000])
			else:
				await message.channel.send("No messages found with `{0}`!".format(text_one))
		except discord.Forbidden:
			return

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.author.bot:
			return
		if (self.bot.self_bot and message.content.startswith('re/') and await self.bot.is_owner(message.author)) or (not self.bot.self_bot and message.content.startswith('sed/')):
				if message.guild and not message.guild.me.permissions_in(message.channel).send_messages:
					return
				await self.do_sed(message)

	@commands.command(aliases=['webshot', 'ss'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def screenshot(self, ctx, url:str):
		"""Retrieve a screenshot of a site"""
		if not url.startswith('http'):
			url = f"http://{url}"
		t = time.time()
		img = await self.f_api(ctx.command.name, text=url)
		if not img:
			return await ctx.send('\N{WARNING SIGN} `Timed out/Failed to screenshot site!`')
		f = 'screenshot.png'
		e = discord.Embed().set_image(url=f'attachment://{f}')
		e.title = url[:256]
		e.set_footer(text='\N{ALARM CLOCK} Took {:.01f}s'.format(time.time() - t))
		await ctx.send(file=img, filename=f, embed=e)

	@commands.command(aliases=['rcount'])
	async def rolecount(self, ctx, *, role:str):
		role = role.lower()
		for r in ctx.guild.roles:
			if r.is_default():
				continue
			elif r.name.lower() in role or r.name.lower() == role:
				role = r
				break
		if not isinstance(role, discord.Role):
			return await ctx.send('\N{NO ENTRY} `Role not found.`')
		count = sum(1 for m in ctx.guild.members if r in m.roles)
		await ctx.send(f'There are **{count}** members in the role `{role.name}`')

	@commands.group(name='hash', invoke_without_command=True)
	async def hash_cmd(self, ctx, *, txt:str):
		"""MD5 Encrypt Text"""
		md5 = hashlib.md5(txt.encode()).hexdigest()
		await ctx.send('**MD5**\n'+md5)

	@hash_cmd.command(name='sha1')
	async def hash_sha1(self, ctx, *, txt:str):
		"""SHA1 Encrypt Text"""
		sha = hashlib.sha1(txt.encode()).hexdigest()
		await ctx.send('**SHA1**\n'+sha)

	@hash_cmd.command(name='sha256')
	async def hash_sha256(self, ctx, *, txt:str):
		"""SHA256 Encrypt Text"""
		sha256 = hashlib.sha256(txt.encode()).hexdigest()
		await ctx.send('**SHA256**\n'+sha256)

	@hash_cmd.command(name='sha512')
	async def hash_sha512(self, ctx, *, txt:str):
		"""SHA512 Encrypt Text"""
		sha512 = hashlib.sha512(txt.encode()).hexdigest()
		await ctx.send('**SHA512**\n'+sha512)

	async def spam_check(self, ctx, text, c=False):
		if len(text) < 4:
			return await ctx.send('\N{WARNING SIGN} `Feedback must be longer than 3 characters.`')
		split = text.split()
		if c and len(split) <= 3:
			return await ctx.send("\N{WARNING SIGN} `3 words or less isn't a very long compliment` \N{FROWNING FACE WITH OPEN MOUTH}")
		elif len(split) == 1:
			return await ctx.send("\N{WARNING SIGN} `1 word isn't very constructive feedback.`")
		elif len(split) >= 2 and len([x for x in split if x == split[0]]) == len(split):
			return await ctx.send('\N{WARNING SIGN} `Quit spamming the same thing.`')
		elif self.bad_status.search(text):
			return await ctx.send('\N{NO ENTRY} that server blows lmao.')
		elif c:
			load = await self.perspective_api(ctx, text, ("TOXICITY",))
			if load is False:
				return
			elif round(load['attributeScores']['TOXICITY']['summaryScore']['value'] * 100) >= 10:
				return await ctx.send(
					'\N{FROWNING FACE WITH OPEN MOUTH} thats ' \
					'\N{FROWNING FACE WITH OPEN MOUTH} not ' \
					'\N{FROWNING FACE WITH OPEN MOUTH} very ' \
					'\N{FROWNING FACE WITH OPEN MOUTH} nice ' \
					'\N{FROWNING FACE WITH OPEN MOUTH}'
				)
		return False

	async def insert_complaint(self, ctx, c=False):
		db = 'compliment' if c else 'feedback'
		sql = f'INSERT INTO `{db}` (`shard`, `user`, `channel`) VALUES (%s, %s, %s)'
		await self.cursor.execute(sql, (
			ctx.guild.shard_id if ctx.guild else 0,
			ctx.author.id, ctx.channel.id
		))
		sql = f'SELECT `id` FROM `{db}` ORDER BY id DESC LIMIT 1'
		q = await self.cursor.execute(sql)
		return int((await q.fetchone())['id'])

	@commands.group(aliases=['feedback', 'contact'], invoke_without_command=True)
	@commands.cooldown(1, 15, commands.BucketType.guild)
	async def complain(self, ctx, *, text:str):
		"""Leave a complaint or feedback concerning the bot (or NotSoSuper)"""
		if await self.spam_check(ctx, text):
			return
		f_id = await self.insert_complaint(ctx)
		msg = """
**Feedback #__{5}__**
Shard: `{6}`
User: **{0}** `<{0.id}>`
Guild: `{1} <{7}>`{2}
Time: __{3}__
Message:```\n{4}\n```
""".format(ctx.author,
					 ctx.guild.name if ctx.guild else 'Private Message',
					 "\nChannel: `{0.name} <{0.id}>`".format(ctx.channel) if ctx.guild else '',
					 ctx.message.created_at.strftime('%m/%d/%Y %H:%M:%S'),
					 text, f_id,
					 ctx.guild.shard_id if ctx.guild else 0,
					 ctx.guild.id if ctx.guild else 'N/A')
		if len(msg) >= 2000:
			msg = msg[:1997]+'```'
		c = discord.Object(id=186704399677128704)
		await self.bot.send_message(c, msg, replace_mentions=True)
		await ctx.send("The NotSoBot Security Agency (NSA) has been notified.")

	@complain.command(name='respond')
	@commands.is_owner()
	async def complain_respond(self, ctx, f_id, *, text:str):
		if f_id == '|' or f_id == 'latest':
			sql = 'SELECT `id` FROM `feedback` ORDER BY id DESC LIMIT 1'
			q = await self.cursor.execute(sql)
			f_id = (await q.fetchone())['id']
		sql = 'SELECT user,channel FROM `feedback` WHERE id={0}'.format(f_id)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		if not result:
			return await ctx.send('Invalid Feedback ID!')
		c = discord.Object(id=result['channel'])
		try:
			await self.bot.send_message(c, '<@{0}> **In Response to Feedback #__{1}__**\n{2}'.format(result['user'], f_id, text), replace_mentions=False)
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Sent response!')
		except:
			await ctx.send('\N{WARNING SIGN} Error sending response.')

	@commands.command()
	@commands.cooldown(1, 15, commands.BucketType.guild)
	async def compliment(self, ctx, *, text:str):
		if await self.spam_check(ctx, text, c=True):
			return
		f_id = await self.insert_complaint(ctx, c=True)
		msg = """
**Compliment #__{5}__**
Shard: `{6}`
User: **{0}** `<{0.id}>`
Guild: `{1} <{7}>`{2}
Time: __{3}__
Message:```\n{4}\n```
""".format(ctx.author,
					 ctx.guild.name if ctx.guild else 'Private Message',
					 "\nChannel: `{0.name} <{0.id}>`".format(ctx.channel) if ctx.guild else '',
					 ctx.message.created_at.strftime('%m/%d/%Y %H:%M:%S'),
					 text, f_id,
					 ctx.guild.shard_id if ctx.guild else 0,
					 ctx.guild.id if ctx.guild else 'N/A')
		if len(msg) >= 2000:
			msg = msg[:1997]+'```'
		c = discord.Object(id=341713308132311060)
		await self.bot.send_message(c, msg, replace_mentions=True)
		await ctx.send("ok, left compliment \N{SMILING FACE WITH OPEN MOUTH}")

	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.user)
	async def undo(self, ctx, count:int=1):
		"""Undo your last command messages"""
		if count > 5:
			return await ctx.send('\N{NO ENTRY} `Can only undo <= 5 command messages at a time.`')
		check = ctx.guild and ctx.channel.permissions_for(ctx.guild.me).manage_messages
		to_delete = []
		cmds = self.bot.command_messages.copy()

		try:
			for _ in range(count):
				msgs = list(filter(lambda x: ctx.author.id == cmds[x][0][3], cmds))
				assert msgs
				bot_messages = None
				for idx in reversed(range(len(msgs) - 1)):
					msg = msgs[idx]
					bot_messages = cmds[msg][0][2]
					if bot_messages:
						break
				assert bot_messages
				if check:
					bot_messages.append(msg)
				to_delete += bot_messages
				del cmds[msg]
			await ctx.delete(*set(to_delete))
		except (AssertionError, discord.NotFound):
			await ctx.send('\N{NO ENTRY SIGN} No previous invoked commands found.', delete_after=5)
		else:
			del cmds[ctx.message.id]
			await ctx.send(
				f"\N{WHITE HEAVY CHECK MARK} Deleted last{f' {count}' if count > 1 else ''} command message(s).",
				delete_after=1.5
			)
		finally:
			if check:
				await ctx.delete(ctx.message)

	@commands.command(aliases=['char'])
	async def charinfo(self, ctx, *chars:str):
		"""Unicode character information"""
		if not chars:
			return await ctx.send('\N{NO ENTRY} `Characters required.`')
		j = ''.join(chars)
		if len(j) > 15:
			return await ctx.send('\N{NO ENTRY SIGN} Too many characters ({0}/15)'.format(len(j)))
		msg = ''
		chars = [x for x in chars for x in x]
		for char in chars:
			name = unicodedata.name(char, False)
			if not name:
				return await ctx.send('\N{WARNING SIGN} Character not found.')
			u = format(ord(char), 'x')
			esc = '`\\U{0:>08}`'.format(u)
			url = f'http://www.fileformat.info/info/unicode/char/{u}'
			msg += "{0}: **{1}** - {2} \N{EM DASH} {3}{4}".format(esc, name, char, url, '\n' if len(chars) > 1 else '')
		await ctx.send(msg)

	@commands.command(aliases=['calc'])
	async def calculate(self, ctx, *, expr:str):
		expr = quote(expr)
		result = await self.get_text(f"https://f.ggg.dev/api/calculator/evaluate?expression={expr}")
		await ctx.send(self.format_code(result))


def setup(bot):
	bot.add_cog(Utils(bot))
