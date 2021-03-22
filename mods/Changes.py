import asyncio
from collections import deque

import discord
from discord.ext import commands

from mods.cog import Cog
from utils.funcs import LimitedDict
from utils.paginator import CannotPaginate, Pages


class Changes(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.hastebin = bot.funcs.hastebin
		# self.lock = asyncio.Lock(loop=bot.loop)
		# if 0 in bot.shard_ids:
		# 	self.name_logs = LimitedDict(maxlen=500)

	@commands.command(aliases=['name', 'namelogs'])
	@commands.cooldown(1, 5)
	async def names(self, ctx, *, user:discord.User=None):
		"""Show all the logs the bot has of the users name or nickname"""
		user = ctx.author if user is None else user
		sql = "SELECT * FROM `names` WHERE user={0.id}".format(user)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		entries = []
		nick_changed = False
		for s in result:
			name = s['name']
			time = '`{0}`'.format(s['time'].strftime("%m-%d-%Y %I:%M %p"))
			if s['discrim']:
				entries.append('[Discrim] "{0}" `#{1}` => `#{2}` {3}'.format(name, s['discrim'], s['new_discrim'], time))
			elif s['nick']:
				if ctx.guild is not None and s['guild'] == ctx.guild.id:
					entries.append('[Nick] "{0}" `{1}`'.format(name, time))
					if not nick_changed:
						nick_changed = True
			else:
				entries.append('"{0}" `{1}`'.format(name, time))
		if not entries:
			return await ctx.send("\N{NO ENTRY} \"{0}\" does not have any name changes recorded!".format(user.name))
		try:
			assert len(entries) <= 120
			p = Pages(ctx, entries=list(reversed(entries)), per_page=20, extra_info='All times are EST')
			if nick_changed:
				p.embed.title = 'Name/Nickname Logs'
			else:
				p.embed.title = 'Name Logs'
			p.embed.color = 0x738bd7
			p.embed.set_author(name=user.display_name, icon_url=user.avatar_url or user.default_avatar_url)
			await p.paginate()
		except (CannotPaginate, AssertionError):
			joined = '\n'.join(entries).replace('`', '').replace('*', '-')
			if len(joined) > 2000:
				joined = f"{user} - Name/Nickname Logs\n\n{joined}"
				url = await self.hastebin(joined)
				await ctx.send(f"\N{WARNING SIGN} `Results too long, uploaded to hastebin:` {url}")
			else:
				await ctx.send(joined)

	@commands.command(aliases=['guildnames', 'gnames'])
	@commands.cooldown(1, 15)
	@commands.guild_only()
	async def snames(self, ctx, *, guild:discord.Guild=None):
		"""Show all the logs the bot has of the guilds name"""
		try:
			guild = guild or ctx.guild
			sql = f"SELECT name,time FROM `guild_names` WHERE guild={guild.id}"
			q = await self.cursor.execute(sql)
			result = await q.fetchall()
			if not result:
				return await ctx.send(f"\N{NO ENTRY} Guild \"{guild.name}\" does not have any name changes recorded!")
			entries = []
			for s in result:
				entries.append("\"{0}\" `{1}`".format(
					s['name'],
					s['time'].strftime("%m-%d-%Y %I:%M %p")
				))
			assert len(entries) <= 120
			p = Pages(ctx, entries=list(reversed(entries)), per_page=20, extra_info='All times are EST')
			p.embed.title = 'Server Name Logs'
			p.embed.color = 0x738bd7
			p.embed.set_author(name=guild.name, icon_url=guild.icon_url or None)
			await p.paginate()
		except (CannotPaginate, AssertionError):
			joined = '\n'.join(entries).replace('`', '').replace('*', '-')
			if len(joined) > 2000:
				joined = f"{guild} - Server Name Logs\n\n{joined}"
				url = await self.hastebin(joined)
				await ctx.send(f"\N{WARNING SIGN} `Results too long, uploaded to hastebin:` {url}")
			else:
				await ctx.send(joined)

	# @commands.Cog.listener()
	# async def on_member_update(self, before, after):
	# 	await self.bot.wait_until_ready()
	# 	if before.discriminator == after.discriminator and before.name == after.name and before.nick == after.nick:
	# 		return
	# 	data = {
	# 		'user': [
	# 			before.id,
	# 			before.guild.id
	# 		],
	# 		'before': [
	# 			before.name,
	# 			before.nick,
	# 			before.discriminator
	# 		],
	# 		'after': [
	# 			after.name,
	# 			after.nick,
	# 			after.discriminator
	# 		]
	# 	}
	# 	if 0 in self.bot.shard_ids:
	# 		await self.parse_presence_update(data)
	# 	else:
	# 		await self.bot.rpc.publish({'command': 'presence_update', 'data': data}, None)
	# 	del data

	# @commands.Cog.listener()
	# async def on_rpc_receive(self, data):
	# 	if 0 not in self.bot.shard_ids:
	# 		return
	# 	payload = data.get('payload')
	# 	if payload:
	# 		if payload.get('command') == 'presence_update':
	# 			await self.parse_presence_update(payload['data'])

	# async def execute(self, sql, args):
	# 	#to prevent multiple loggings of the same name from multiple guilds sending presence updates
	# 	user = args[0]
	# 	name = args[2]
	# 	if user in self.name_logs:
	# 		logs = self.name_logs[user]
	# 	else:
	# 		self.name_logs[user] = deque(maxlen=15)
	# 		logs = self.name_logs[user]
	# 	logs.append(name)
	# 	if len(logs) > 1 and logs[-2] == name:
	# 		return
	# 	await self.cursor.execute(sql, args)

	# async def parse_presence_update(self, data):
	# 	user, before, after = data['user'], data['before'], data['after']
	# 	user_id, guild_id = user
	# 	old_name, old_nick, old_discrim = before
	# 	new_name, new_nick, new_discrim = after
	# 	async with self.lock:
	# 		if old_discrim != new_discrim:
	# 			sql = "INSERT INTO `names` (`user`, `guild`, `name`, `nick`, `discrim`, `new_discrim`) VALUES (%s, %s, %s, %s, %s, %s)"
	# 			await self.execute(sql, (user_id, guild_id, new_name, False, old_discrim, new_discrim))
	# 		sql = "INSERT INTO `names` (`user`, `guild`, `name`, `nick`) VALUES (%s, %s, %s, %s)"
	# 		if old_name != new_name:
	# 			q = await self.cursor.execute(f'SELECT * FROM `names` WHERE user={user_id} LIMIT 1')
	# 			check = await q.fetchone()
	# 			if not check:
	# 				await self.execute(sql, (user_id, guild_id, old_name, False))
	# 			if old_discrim == new_discrim:
	# 				await self.execute(sql, (user_id, guild_id, new_name, False))
	# 		elif old_nick or (old_nick is None and new_nick):
	# 			if old_nick != new_nick and new_nick:
	# 				await self.execute(sql, (user_id, guild_id, new_nick, True))

	@commands.Cog.listener()
	async def on_guild_update(self, before, after):
		if before.name != after.name:
			check = f'SELECT guild FROM `guild_names` WHERE guild={before.id} LIMIT 1'
			q = await self.cursor.execute(check)
			result = await q.fetchall()
			sql = "INSERT INTO `guild_names` (`guild`, `name`) VALUES (%s, %s)"
			if not result:
				await self.cursor.execute(sql, (before.id, before.name))
			await self.cursor.execute(sql, (before.id, after.name))

def setup(bot):
	if not bot.self_bot:
		bot.add_cog(Changes(bot))
