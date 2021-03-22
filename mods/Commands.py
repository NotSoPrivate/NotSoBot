import sys

import discord
from discord.ext import commands

from mods.cog import Cog
from utils import checks
from utils.funcs import query_prefix
from utils.paginator import CannotPaginate, Pages


class Commands(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.truncate = bot.funcs.truncate
		self.find_member = bot.funcs.find_member
		self.good_modules = ['mods.Debug', 'mods.Stats', 'mods.Commands', 'mods.cog']
		self.good_commands = ['command', 'blacklist', 'help', 'invite']

	@commands.group(aliases=['setprefix', 'changeprefix'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def prefix(self, ctx, *, txt:str=None):
		"""Change the Bots Prefix for the Guild"""
		if txt is None:
			clause =  f"WHERE guild={ctx.guild.id}"
			sql = f"SELECT * FROM `prefix` {clause} AND d"
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			sql = f"SELECT * FROM `prefix_channel` {clause} AND channel={ctx.channel.id}"
			q = await self.cursor.execute(sql)
			result2 = await q.fetchone()
			if not result:
				guild_prefix = '.'
			else:
				guild_prefix = result['prefix']
			if not result2:
				channel_prefix = None
			else:
				channel_prefix = result2['prefix']
			msg = "Guild Prefix: `{0}`\n".format(guild_prefix)
			if channel_prefix != None:
				msg += "**Current** Channel Prefix: `{0}`".format(channel_prefix)
			await ctx.send(msg)
		else:
			q = await self.cursor.execute('SELECT id FROM `prefix` WHERE guild=%s AND prefix=%s', (ctx.guild.id, txt))
			if await q.fetchone():
				return await ctx.send('\N{NO ENTRY} Prefix already exists.')
			sql = "SELECT guild FROM `prefix` WHERE guild={0} AND d".format(ctx.guild.id)
			q = await self.cursor.execute(sql)
			if not await q.fetchone():
				sql = "INSERT INTO `prefix` (`guild`, `prefix`, `d`) VALUES (%s, %s, %s)"
				await self.cursor.execute(sql, (ctx.guild.id, txt, 1))
				await ctx.send("\N{WHITE HEAVY CHECK MARK} Set bot prefix to \"{0}\" for the guild.".format(txt))
			else:
				update_sql = "UPDATE `prefix` SET prefix=%s WHERE guild=%s"
				await self.cursor.execute(update_sql, (txt, ctx.guild.id))
				await ctx.send("\N{WHITE HEAVY CHECK MARK} Updated bot prefix to \"{0}\" for the guild.".format(txt))

			query_prefix.invalidate(self.bot, ctx.guild.id)

	@prefix.command(name='add')
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def prefix_add(self, ctx, *, txt:str):
		"""Add an extra guild prefix for the bot"""
		if txt == '.' or txt == ctx.guild.me.mention:
			return await ctx.send('\N{NO ENTRY} Cannot add default prefix.')
		sql = 'SELECT COUNT(id) FROM `prefix` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		if (await q.fetchone())['COUNT(id)'] >= 20:
			return await ctx.send('\N{WARNING SIGN} Maximum number of prefixes reached (>= 20).')
		sql = 'SELECT id FROM `prefix` WHERE guild=%s AND prefix=%s'
		q = await self.cursor.execute(sql, (ctx.guild.id, txt))
		if await q.fetchone():
			await ctx.send('\N{NO ENTRY} Prefix already exists.')
		else:
			sql = "INSERT INTO `prefix` (`guild`, `prefix`, `d`) VALUES (%s, %s, %s)"
			await self.cursor.execute(sql, (ctx.guild.id, txt, 0))
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Added guild prefix.')
			query_prefix.invalidate(self.bot, ctx.guild.id)

	@prefix.command(name='list')
	@commands.guild_only()
	@commands.cooldown(1, 10, commands.BucketType.guild)
	async def prefix_list(self, ctx):
		"""List all bot prefixes"""
		q = await self.cursor.execute('SELECT * FROM `prefix` WHERE guild=%s', (ctx.guild.id,))
		sp = await q.fetchall()
		q = await self.cursor.execute('SELECT * FROM `prefix_channel` WHERE guild=%s', (ctx.guild.id,))
		cp = await q.fetchall()
		if not sp and not cp:
			return await ctx.send('\N{WARNING SIGN} Guild does not have any custom set prefixes.')
		entries = []
		for x in sp:
			if x['d']:
				entries.append('Guild Prefix: "{0}" (Default)'.format(x['prefix']))
			else:
				entries.append('Guild Prefix: "{0}"'.format(x['prefix']))
		for x in cp:
			c = ctx.guild.get_channel(x['channel'])
			if c:
				entries.append('{0} Prefix: "{1}"'.format(c.mention, x['prefix']))
		try:
			p = Pages(ctx, entries=entries, per_page=15)
			p.embed.title = 'Prefixes'
			p.embed.color = 0x738bd7
			p.embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url)
			await p.paginate()
		except CannotPaginate:
			await self.truncate(ctx.channel, '\N{WHITE HEAVY CHECK MARK} **Prefixes**\n{0}'.format('\n'.join(entries)))

	@prefix.command(name='delete', aliases=['remove'])
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def prefix_delete(self, ctx, *, txt:str):
		"""Delete a guild prefix"""
		sql = 'SELECT id FROM `prefix` WHERE guild=%s AND prefix=%s'
		q = await self.cursor.execute(sql, (ctx.guild.id, txt))
		check = await q.fetchone()
		if not check:
			await ctx.send('\N{NO ENTRY} Prefix does not exists.')
		else:
			sql = "DELETE FROM `prefix` WHERE id=%s"
			await self.cursor.execute(sql, (check['id'],))
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Removed prefix.')

			query_prefix.invalidate(self.bot, ctx.guild.id)

	@prefix.command(name='channel')
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def prefix_channel(self, ctx, *, txt:str):
		"""Change the Bots Prefix for the current Channel"""
		channel = ctx.channel
		for c in ctx.message.channel_mentions:
			channel = c
			txt = txt.replace(channel.mention, '').replace('#'+channel.name, '')
		sql = "INSERT INTO `prefix_channel` (`guild`, `prefix`, `channel`) VALUES (%s, %s, %s)"
		update_sql = "UPDATE `prefix_channel` SET prefix=%s WHERE guild=%s AND channel=%s"
		check = "SELECT * FROM `prefix_channel` WHERE guild={0} AND channel={1}"
		check = check.format(ctx.guild.id, channel.id)
		q = await self.cursor.execute(check)
		result = await q.fetchall()
		if not result:
			await self.cursor.execute(sql, (ctx.guild.id, txt, channel.id))
			await ctx.send("\N{WHITE HEAVY CHECK MARK} Set bot prefix to \"{0}\" for {1}".format(txt, channel.mention))
		else:
			await self.cursor.execute(update_sql, (txt, ctx.guild.id, channel.id))
			await ctx.send("\N{WHITE HEAVY CHECK MARK} Updated bot prefix to \"{0}\" for {1}".format(txt, channel.mention))

		query_prefix.invalidate(self.bot, ctx.channel.id, channel=True)

	@prefix.group(name='reset', invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(1, 10, commands.BucketType.guild)
	async def prefix_reset(self, ctx):
		"""Reset All Custom Set Prefixes For the Bot"""
		check = "SELECT * FROM `prefix` WHERE guild={0}".format(ctx.guild.id)
		q = await self.cursor.execute(check)
		result = await q.fetchall()
		if not result:
			await ctx.send("\N{NO ENTRY} Current guild does **not** have a custom prefix set!")
		else:
			sql = "DELETE FROM `prefix` WHERE guild={0}".format(ctx.guild.id)
			await self.cursor.execute(sql)
			await ctx.send("\N{HEAVY EXCLAMATION MARK SYMBOL} **Reset guild prefix**\nThis does not reset channel prefixes, run \"all\" after reset to reset all prefixes *or* \"channels\" to reset all custom channel prefixes.")
			query_prefix.invalidate(self.bot, ctx.guild.id)


	@prefix_reset.command(name='channel')
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(1, 10, commands.BucketType.guild)
	async def prefix_reset_channel(self, ctx, channel:discord.TextChannel=None):
		if channel is None:
			channel = ctx.channel
		check = "SELECT * FROM `prefix_channel` WHERE guild={0} AND channel={1}".format(ctx.guild.id, channel.id)
		q = await self.cursor.execute(check)
		result = await q.fetchall()
		if not result:
			await ctx.send("\N{NO ENTRY} {0} does **not** have a custom prefix Set!\nMention the channel after \"reset channel\" for a specific channel.".format(channel.mention))
		else:
			sql = "DELETE FROM `prefix_channel` WHERE guild={0} AND channel={1}".format(ctx.guild.id, channel.id)
			await self.cursor.execute(sql)
			await ctx.send("\N{HEAVY EXCLAMATION MARK SYMBOL} Reset {0}'s prefix!\nThis does **not** reset all custom channel prefixes, \"reset channels\" to do so.".format(channel.mention))
			query_prefix.invalidate(self.bot, ctx.channel.id, channel=True)

	@prefix_reset.command(name='channels')
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(1, 10, commands.BucketType.guild)
	async def prefix_reset_channels(self, ctx):
		check = "SELECT * FROM `prefix_channel` WHERE guild={0}".format(ctx.guild.id)
		q = await self.cursor.execute(check)
		result = await q.fetchall()
		if not result:
			await ctx.send("\N{NO ENTRY} Guild does **not** reset a custom prefix set for any channel!\nMention the channel after \"reset channel\" for a specific channel.")
		else:
			sql = "DELETE FROM `prefix_channel` WHERE guild={0}".format(ctx.guild.id)
			await self.cursor.execute(sql)
			await ctx.send("\N{HEAVY EXCLAMATION MARK SYMBOL} Reset all channels custom prefixes!")
			for channel in ctx.guild.channels:
				query_prefix.invalidate(self.bot, channel.id, channel=True)

	@prefix_reset.command(name='all', aliases=['everything'])
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(1, 10, commands.BucketType.guild)
	async def prefix_reset_all(self, ctx):
		await self.cursor.execute("DELETE FROM `prefix_channel` WHERE guild={0}".format(ctx.guild.id))
		await self.cursor.execute("DELETE FROM `prefix` WHERE guild={0}".format(ctx.guild.id))
		query_prefix.invalidate(self.bot, ctx.guild.id)
		for channel in ctx.guild.channels:
			query_prefix.invalidate(self.bot, channel.id, channel=True)
		await ctx.send("\N{WARNING SIGN} Reset all custom guild prefix settings!")

	async def command_toggle(self, t:str, ctx, cmd:str, user=None, msg=True):
		cmd = str(self.bot.all_commands[cmd])
		if cmd in self.good_commands:
			return await ctx.send('\N{NO ENTRY} You cannot disable command: `{0}`!'.format(self.good_commands[self.good_commands.index(cmd)]))
		elif not msg:
			enabled = False
		if t == 'guild':
			sql = "SELECT * FROM `command_blacklist` WHERE type=1 AND guild=%s AND command=%s"
			q = await self.cursor.execute(sql, (ctx.guild.id, cmd))
			result = await q.fetchone()
			if not result:
				sql = 'INSERT INTO `command_blacklist` (`command`, `type`, `guild`) VALUES (%s, %s, %s)'
				await self.cursor.execute(sql, (cmd, 1, ctx.guild.id))
				if msg:
					await ctx.send(':negative_squared_cross_mark: Disabled command `{0}`.'.format(cmd))
			else:
				enabled = True
				sql = "DELETE FROM `command_blacklist` WHERE type=1 AND guild=%s AND command=%s"
				await self.cursor.execute(sql, (ctx.guild.id, cmd))
				if msg:
					await ctx.send('\N{WHITE HEAVY CHECK MARK} Enabled command `{0}`.'.format(cmd))
		elif t == 'channel':
			channel = user
			sql = "SELECT * FROM `command_blacklist` WHERE type=2 AND guild=%s AND channel=%s AND command=%s"
			q = await self.cursor.execute(sql, (ctx.guild.id, channel.id, cmd))
			result = await q.fetchone()
			if not result:
				sql = 'INSERT INTO `command_blacklist` (`command`, `type`, `guild`, `channel`) VALUES (%s, %s, %s, %s)'
				await self.cursor.execute(sql, (cmd, 2, ctx.guild.id, channel.id))
				if msg:
					await ctx.send(':negative_squared_cross_mark: Disabled command `{0}` for channel {1}.'.format(cmd, channel.mention))
			else:
				enabled = True
				sql = "DELETE FROM `command_blacklist` WHERE type=2 AND guild=%s AND channel=%s AND command=%s"
				await self.cursor.execute(sql, (ctx.guild.id, channel.id, cmd))
				if msg:
					await ctx.send('\N{WHITE HEAVY CHECK MARK} Enabled command `{0}` for channel {1}.'.format(cmd, channel.mention))
		elif t == 'user':
			sql = "SELECT * FROM `command_blacklist` WHERE type=3 AND guild=%s AND user=%s AND command=%s"
			q = await self.cursor.execute(sql, (ctx.guild.id, user.id, cmd))
			result = await q.fetchone()
			if not result:
				sql = 'INSERT INTO `command_blacklist` (`command`, `type`, `guild`, `user`) VALUES (%s, %s, %s, %s)'
				await self.cursor.execute(sql, (cmd, 3, ctx.guild.id, user.id))
				if msg:
					await ctx.send(':negative_squared_cross_mark: Disabled command `{0}` for user `{1}`.'.format(cmd, user))
			else:
				enabled = True
				sql = "DELETE FROM `command_blacklist` WHERE type=3 AND guild=%s AND user=%s AND command=%s"
				await self.cursor.execute(sql, (ctx.guild.id, user.id, cmd))
				if msg:
					await ctx.send('\N{WHITE HEAVY CHECK MARK} Enabled command `{0}` for user `{1}`.'.format(cmd, user))
		elif t == 'role':
			role = user
			sql = "SELECT * FROM `command_blacklist` WHERE type=4 AND guild=%s AND role=%s AND command=%s"
			q = await self.cursor.execute(sql, (ctx.guild.id, role.id, cmd))
			result = await q.fetchone()
			if not result:
				sql = 'INSERT INTO `command_blacklist` (`command`, `type`, `guild`, `role`) VALUES (%s, %s, %s, %s)'
				await self.cursor.execute(sql, (cmd, 4, ctx.guild.id, role.id))
				if msg:
					await ctx.send(':negative_squared_cross_mark: Disabled command `{0}` for role {1}.'.format(cmd, role.mention))
			else:
				enabled = True
				sql = "DELETE FROM `command_blacklist` WHERE type=4 AND guild=%s AND role=%s AND command=%s"
				await self.cursor.execute(sql, (ctx.guild.id, role.id, cmd))
				if msg:
					await ctx.send('\N{WHITE HEAVY CHECK MARK} Enabled command `{0}` for role {1}.'.format(cmd, role.mention))
		elif t == 'global':
			sql = "SELECT * FROM `command_blacklist` WHERE type=0 AND command=%s"
			q = await self.cursor.execute(sql, (cmd,))
			result = await q.fetchone()
			if not result:
				sql = 'INSERT INTO `command_blacklist` (`command`, `type`) VALUES (%s, %s)'
				await self.cursor.execute(sql, (cmd, 0))
				if msg:
					await ctx.send(':globe_with_meridians: Disabled command `{0}` globally.'.format(cmd))
			else:
				enabled = True
				sql = "DELETE FROM `command_blacklist` WHERE type=0 AND command=%s"
				await self.cursor.execute(sql, (cmd,))
				if msg:
					await ctx.send('\N{WHITE HEAVY CHECK MARK} Enabled command `{0}` globally.'.format(cmd))
		if not msg:
			return enabled

	async def module_command_toggle(self, module, t:str, ctx, chan=None):
		disabled_count = 0
		enabled_count = 0
		for command in self.bot.commands:
			if command.module == module.__name__:
				r = await self.command_toggle(t, ctx, str(command), chan, msg=False)
				if r:
					enabled_count += 1
				else:
					disabled_count += 1
		return enabled_count, disabled_count

	async def get_modules(self):
		modules = []
		for module in sys.modules:
			if module.startswith('mods.'):
				if module in self.good_modules:
					continue
				mod = module.replace('mods.', '')
				modules.append(mod)
		return modules

	@commands.group(invoke_without_command=True, aliases=['commands', 'cmd'])
	@commands.guild_only()
	@commands.cooldown(1, 3)
	@checks.admin_or_perm(manage_guild=True)
	async def command(self, ctx, *cmds:str):
		"""Toggle a command for the guild"""
		for cmd in cmds[:5]:
			if cmd in self.bot.all_commands:
				await self.command_toggle('guild', ctx, cmd)
			else:
				await ctx.send('\N{NO ENTRY} `Command does not exist.`')

	@command.command(name='user', aliases=['member'])
	@commands.guild_only()
	@commands.cooldown(1, 3)
	@checks.admin_or_perm(manage_guild=True)
	async def command_user(self, ctx, cmd:str, user:discord.User=None):
		"""Toggle Command for a user"""
		if user is None:
			user = ctx.author
		if cmd in self.bot.all_commands:
			await self.command_toggle('user', ctx, cmd, user)
		else:
			await ctx.send('\N{NO ENTRY} `Command does not exist.`')

	@command.command(name='role', aliases=['rank'])
	@commands.guild_only()
	@commands.cooldown(1, 3)
	@checks.admin_or_perm(manage_guild=True)
	async def command_role(self, ctx, cmd:str, role:discord.Role):
		"""Toggle Command for a role"""
		if cmd in self.bot.all_commands:
			await self.command_toggle('role', ctx, cmd, role)
		else:
			await ctx.send('\N{NO ENTRY} `Command does not exist.`')

	@command.command(name='channel')
	@commands.guild_only()
	@commands.cooldown(1, 3)
	@checks.admin_or_perm(manage_guild=True)
	async def command_channel(self, ctx, cmd:str, chan:discord.TextChannel=None):
		"""Toggle Command for a channel"""
		if chan is None:
			chan = ctx.channel
		if cmd in self.bot.all_commands:
			await self.command_toggle('channel', ctx, cmd, chan)
		else:
			await ctx.send('\N{NO ENTRY} `Command does not exist.`')

	@command.command(name='global')
	@commands.is_owner()
	async def command_global(self, ctx, *cmds:str):
		"""Toggle command globally"""
		for cmd in cmds:
			if cmd in self.bot.all_commands:
				await self.command_toggle('global', ctx, cmd)
			else:
				await ctx.send('\N{NO ENTRY} `Command does not exist.`')

	@command.group(name='module', invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	@commands.cooldown(1, 15)
	async def command_module(self, ctx, module:str, chan:discord.TextChannel=None):
		"""Toggle a bot command module"""
		try:
			mod = sys.modules['mods.{0}'.format(module)]
		except KeyError:
			await ctx.send('\N{NO ENTRY} Invalid Module\n**Modules**\n`{0}`'.format(', '.join(await self.get_modules())))
		else:
			if chan:
				count = await self.module_command_toggle(mod, 'channel', ctx, chan)
			else:
				count = await self.module_command_toggle(mod, 'guild', ctx)
			msg = f', Enabled **{count[0]}**' if count[0] else ''
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Disabled **{0}**{1} commands in module `{2}`.'.format(count[1], msg, module))

	@command_module.command(name='list')
	@commands.cooldown(1, 10)
	async def command_module_list(self, ctx):
		modules = await self.get_modules()
		await ctx.send(':information_source: **Modules**\n`{0}`'.format(', '.join(modules)))

	@command.command(name='all')
	@commands.guild_only()
	@commands.cooldown(1, 3)
	@checks.admin_or_perm(manage_guild=True)
	async def command_all(self, ctx):
		sql = 'SELECT COUNT(*) FROM `command_blacklist` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		count = (await q.fetchall())[0]['COUNT(*)']
		sql = 'DELETE FROM `command_blacklist` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		await self.cursor.execute(sql)
		await ctx.send('\N{WHITE HEAVY CHECK MARK} Enabled **{0}** guild command(s).'.format(count))

	@command.command(name='list')
	@commands.guild_only()
	@commands.cooldown(1, 5)
	async def command_list(self, ctx):
		sql = f'SELECT * FROM `command_blacklist` WHERE guild={ctx.guild.id}' + (' OR type=0' if await self.bot.is_owner(ctx.author) else '')
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does **not** have any commands blacklisted.')
		entries = []
		for s in result:
			if s['type'] == 0:
				entries.append('\N{GLOBE WITH MERIDIANS} Globally Disabled: `{0}`'.format(s['command']))
			elif s['type'] == 1:
				entries.append('\N{DESKTOP COMPUTER} Command Disabled on Guild: `{0}`'.format(s['command']))
			elif s['type'] == 2:
				entries.append('\N{BLACK RIGHTWARDS ARROW} Command Disabled in <#{0}>: `{1}`'.format(s['channel'] ,s['command']))
			elif s['type'] == 3:
				user = await self.find_member(ctx.message, s['user'])
				entries.append('\N{BUST IN SILHOUETTE} Command Disabled for **{0}**: `{1}`'.format(user, s['command']))
			elif s['type'] == 4:
				entries.append('\N{EIGHT SPOKED ASTERISK} Command Disabled for <@&{0}>: `{1}`'.format(s['role'], s['command']))
		try:
			p = Pages(ctx, entries=entries, per_page=15)
			p.embed.title = 'Commands Disabled'
			p.embed.color = 0x738bd7
			p.embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url)
			await p.paginate()
		except CannotPaginate:
			await self.truncate(ctx.channel, '\N{WHITE HEAVY CHECK MARK} **Commands Disabled**\n{0}'.format('\n'.join(entries)))

def setup(bot):
	bot.add_cog(Commands(bot))
