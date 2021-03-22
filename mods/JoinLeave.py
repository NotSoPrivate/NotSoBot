import discord
from discord.ext import tasks, commands

from mods.cog import Cog
from mods.Core import NotSoContext
from utils import checks


default_join = 'Welcome to **{guild}** - {mention}! You are the {guildcount} member to join.'
default_leave = '**{user}#{discrim}** has left the guild.'

#http://stackoverflow.com/a/16671271
def number_formating(n):
	return str(n) + ("th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))

class JoinLeave(Cog):

	# @tasks.loop(minutes=10.0)
	# async def member_count_updater(self):
	# 	for guild in self.bot.guilds:
	# 		for channel in guild.channels:
	# 			if channel.permissions_for(guild.me).manage_guild

	# def cog_unload(self):
	# 	self.member_count_updater.cancel()

	@commands.group(aliases=['welcomemessage', 'join'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def welcome(self, ctx, *, message:str=None):
		mentions = ctx.message.channel_mentions
		if mentions and message.startswith(mentions[0].mention):
			channel = mentions[0]
			message = message.replace(channel.mention, '').replace(f'#{channel.name}', '')
		else:
			channel = ctx.channel
		sql = 'SELECT guild FROM `welcome` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			if message is None:
				msg = '\N{WHITE HEAVY CHECK MARK} Enabled welcome messages for {0}.'.format(channel.mention)
			else:
				msg = '\N{WHITE HEAVY CHECK MARK} Added welcome message for {0}.'.format(channel.mention)
			sql = 'INSERT INTO `welcome` (`guild`, `channel`, `message`, `user`) VALUES (%s, %s, %s, %s)'
			await self.cursor.execute(sql, (ctx.guild.id, channel.id, message, ctx.author.id))
		else:
			if message is None:
				return await ctx.send('\N{WARNING SIGN} Please input something to edit the welcome message to.\n`welcome clear` to disable welcome messages.')
			msg = '\N{WHITE HEAVY CHECK MARK} Edited welcome message.'
			sql = "UPDATE `welcome` SET message=%s WHERE guild=%s"
			await self.cursor.execute(sql, (message, ctx.guild.id))
		await ctx.send(msg)

	@welcome.command(name='remove', aliases=['delete', 'clear', 'disable', 'off'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def welcome_remove(self, ctx):
		sql = 'SELECT guild FROM `welcome` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does not have welcome messages enabled.')
		sql = 'DELETE FROM `welcome` WHERE guild={0}'.format(ctx.guild.id)
		await self.cursor.execute(sql)
		await ctx.send(':negative_squared_cross_mark: Disabled welcome message.')

	@welcome.command(name='channel', aliases=['setchannel'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def welcome_channel(self, ctx, channel:discord.TextChannel=None):
		sql = 'SELECT channel FROM `welcome` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does not have welcome messages enabled.')
		if channel is None:
			channel = ctx.guild.get_channel(result['channel'])
			if channel is None:
				channel = ctx.channel
			else:
				return await ctx.send('Current Welcome Channel: {0}'.format(channel.mention))
		sql = 'UPDATE `welcome` SET channel={0} WHERE guild={1}'.format(channel.id, ctx.guild.id)
		await self.cursor.execute(sql)
		await ctx.send('\N{WHITE HEAVY CHECK MARK} Changed welcome channel to {0}'.format(channel.mention))

	@commands.group(aliases=['leavemessage'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def leave(self, ctx, *, message:str=None):
		mentions = ctx.message.channel_mentions
		if mentions and message.startswith(mentions[0].mention):
			channel = mentions[0]
			message = message.replace(channel.mention, '').replace(f'#{channel.name}', '')
		else:
			channel = ctx.channel
		sql = 'SELECT guild FROM `leave` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			if message is None:
				msg = '\N{WHITE HEAVY CHECK MARK} Enabled leave messages for {0}.'.format(channel.mention)
			else:
				msg = '\N{WHITE HEAVY CHECK MARK} Added leave message for {0}.'.format(channel.mention)
			sql = 'INSERT INTO `leave` (`guild`, `channel`, `message`, `user`) VALUES (%s, %s, %s, %s)'
			await self.cursor.execute(sql, (ctx.guild.id, channel.id, message, ctx.author.id))
		else:
			if message is None:
				return await ctx.send('\N{WARNING SIGN} Please input something to edit the leave message to.\n`leave clear` to disable leave messages.')
			msg = '\N{WHITE HEAVY CHECK MARK} Edited leave message.'
			sql = "UPDATE `leave` SET message=%s WHERE guild=%s"
			await self.cursor.execute(sql, (message, ctx.guild.id))
		await ctx.send(msg)

	@leave.command(name='remove', aliases=['delete', 'clear', 'disable', 'off'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def leave_remove(self, ctx):
		sql = 'SELECT guild FROM `leave` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does not have leave messages enabled.')
		sql = 'DELETE FROM `leave` WHERE guild={0}'.format(ctx.guild.id)
		await self.cursor.execute(sql)
		await ctx.send(':negative_squared_cross_mark: Disabled leave message.')

	@leave.command(name='channel', aliases=['setchannel'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def leave_channel(self, ctx, channel:discord.TextChannel=None):
		sql = 'SELECT channel FROM `leave` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does not have leave messages enabled.')
		if channel is None:
			channel = ctx.guild.get_channel(result['channel'])
			if channel is None:
				channel = ctx.channel
			else:
				return await ctx.send('Current Leave Channel: {0}'.format(channel.mention))
		sql = 'UPDATE `leave` SET channel={0} WHERE guild={1}'.format(channel.id, ctx.guild.id)
		await self.cursor.execute(sql)
		await ctx.send('\N{WHITE HEAVY CHECK MARK} Changed leave channel to {0}'.format(channel.mention))

	@welcome.command(name='current', aliases=['show'], invoke_without_command=True)
	@commands.guild_only()
	async def welcome_current(self, ctx):
		sql = 'SELECT message FROM `welcome` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does not have welcome messages enabled.')
		msg = result['message']
		await ctx.send(msg or default_join)

	@leave.command(name='current', aliases=['show'], invoke_without_command=True)
	@commands.guild_only()
	async def leave_current(self, ctx):
		sql = 'SELECT message FROM `leave` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does not have leave messages enabled.')
		msg = result['message']
		await ctx.send(msg or default_leave)

	async def remove(self, guild, welcome):
		sql = f"DELETE FROM `{'welcome' if welcome else 'leave'}` WHERE guild={guild.id}"
		await self.cursor.execute(sql)

	#hack to use tag parsers send function and my custom send func for context, THANKS FOR THE RESTFUL API, DANNY.
	async def get_message(self, member, guild, channel, msg, welcome):
		if not msg:
			msg = default_join if welcome else default_leave
		if '{' in msg:
			m = discord.Object(id=channel.id)
			m._state = channel._state
			m.channel = channel
			m.guild = guild
			m.author = member
			ctx = NotSoContext(message=m, prefix=None, bot=self.bot)
			cog = self.bot.get_cog('Tags')
			parser = cog.parse
			kws = ("{guildcount}", "{servercount}", "{membercount}")
			if any(x in msg for x in kws):
				nf = number_formating(guild.member_count)
				for x in kws:
					msg = msg.replace(x, nf)
			msg = await parser(ctx, msg, "")
			await cog.send(ctx, msg, replace_mentions=False, replace_everyone=False)
			del ctx, m
		else:
			await channel.send(msg, replace_mentions=False, replace_everyone=False)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		try:
			guild = member.guild
			sql = 'SELECT * FROM `welcome` WHERE guild={0}'.format(guild.id)
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			if not result:
				return
			channel = guild.get_channel(result['channel'])
			if channel is None:
				await self.remove(guild, True)
			else:
				await self.get_message(member, guild, channel, result['message'], True)
		except (discord.Forbidden, discord.NotFound):
			await self.remove(guild, True)

	@commands.Cog.listener()
	async def on_member_remove(self, member):
		try:
			guild = member.guild
			sql = 'SELECT * FROM `leave` WHERE guild={0}'.format(guild.id)
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			if not result:
				return
			channel = guild.get_channel(result['channel'])
			if channel is None:
				await self.remove(guild, False)
			else:
				await self.get_message(member, guild, channel, result['message'], False)
		except (discord.Forbidden, discord.NotFound):
			await self.remove(guild, False)

def setup(bot):
	bot.add_cog(JoinLeave(bot))
