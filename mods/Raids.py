import datetime
from collections import defaultdict

import discord
from discord.ext import commands
from mods.cog import Cog
from utils import cache, checks
from utils.time import human_timedelta


class Raids(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.mode_map = {'off': 0, 'on': 1, 'strict': 2}
		self.punished = defaultdict(set)
		self.find_member = bot.funcs.find_member
		self.get_default_channel = bot.funcs.get_default_channel

	def mode_string(self, mode:int):
		v = list(self.mode_map.values())
		return v[v.index(mode)]

	async def remove_raid(self, guild):
		self.has_raid.invalidate(self, guild)

		await self.cursor.execute(f'DELETE FROM `raids` WHERE guild={guild}')
		self.punished.pop(guild, None)

	@commands.group(invoke_without_command=True, aliases=['raids'])
	@commands.guild_only()
	@checks.admin_or_perm(kick_members=True)
	async def raid(self, ctx, mode:str=None, channel:discord.TextChannel=None):
		q = await self.cursor.execute(f'SELECT * FROM `raids` WHERE guild={ctx.guild.id}')
		check = await q.fetchone()
		if not check or (mode in self.mode_map and self.mode_map[mode] not in (0, check['mode'])):
			if not channel:
				channel = ctx.channel
			if mode != None:
				if mode.isdigit():
					mode = int(mode)
				else:
					if mode in self.mode_map:
						mode = self.mode_map[mode]
			if mode is None or isinstance(mode, str) or (mode <= 0 or mode > 2):
				return await ctx.send(f"\N{NO ENTRY} Invalid mode (Valid Modes: `{', '.join(self.mode_map.keys())}`).")
			try:
				await ctx.guild.edit(verification_level=discord.VerificationLevel.high)
			except:
				if mode != 2:
					await ctx.send('\N{WARNING SIGN} Could not set guild verifcation level!')
				else:
					return await ctx.send('\N{NO ENTRY} Strict raid mode requires `manage_guild` and `ban_users` permission.')
			
			self.has_raid.invalidate(self, ctx.guild)

			await self.cursor.execute('REPLACE INTO `raids` (`guild`, `channel`, `user`, `mode`) VALUES (%s, %s, %s, %s)', (ctx.guild.id, channel.id, ctx.author.id, mode))
			await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Enabled raid mode.\nLevel: **{self.mode_string(mode)}**\nLogging actions to: {channel.mention}')
		elif check and mode is None:
			user = await self.find_member(ctx.message, check['user'])
			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} **Raid Mode Enabled**\nMode: **{self.mode_string(check['mode'])}**\nAction Log: {ctx.guild.get_channel(check['channel']).mention}\nEnabler: `{user}`\nEnabled: __{check['time'].strftime('%m/%d/%Y %H:%M:%S')}__")
		elif mode and mode in self.mode_map.keys() and self.mode_map[mode] == 0:
			try:
				await ctx.guild.edit(verification_level=discord.VerificationLevel.low)
			except:
				pass
			await self.remove_raid(ctx.guild.id)
			await ctx.send('\N{NEGATIVE SQUARED CROSS MARK} Disabled raid mode.')
		else:
			await ctx.send(f"\N{NO ENTRY} Invalid mode (Valid Modes: `{', '.join(self.mode_map.keys())}`).")

	@raid.command(name='channel')
	@commands.guild_only()
	@checks.admin_or_perm(kick_members=True)
	async def raid_channel(self, ctx, channel:discord.TextChannel=None):
		if not channel:
			channel = ctx.channel
		q = await self.cursor.execute(f'SELECT channel FROM `raids` WHERE guild={ctx.guild.id}')
		check = await q.fetchone()
		if not check:
			await ctx.send('\N{NO ENTRY} Raid mode not enabled on guild.')
		elif check['channel'] == channel.id:
			await ctx.send('\N{WARNING SIGN} You cannot update the action log channel to the current one!')
		else:
			self.has_raid.invalidate(self, ctx.guild)

			await self.cursor.execute(f'UPDATE `raids` SET channel={channel.id} WHERE guild={ctx.guild.id}')
			await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Updated raid action log channel to: {channel.mention}')

	def get_channel(self, guild, gid:int):
		channel = guild.get_channel(gid)
		return channel or self.get_default_channel(guild.me, guild, send_messages=True)

	@commands.group(invoke_without_command=True, aliases=['antimentionspam'])
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def mentionspam(self, ctx, count:int=None, channel:discord.TextChannel=None):
		if count:
			if count > 100:
				return await ctx.send('> 100 mentions lol?')
			elif count <= 3:
				return await ctx.send('\N{WARNING SIGN} Threshold must be greater than 3 mentions.')
		q = await self.cursor.execute(f'SELECT user,count,channel,time FROM `mention_spam` WHERE guild={ctx.guild.id}')
		check = await q.fetchone()
		if not check:
			if not channel:
				channel = ctx.channel
			if not count:
				count = 5
			await self.cursor.execute('INSERT INTO `mention_spam` (`guild`, `channel`, `count`, `user`) VALUES (%s, %s, %s, %s)', (ctx.guild.id, channel.id, count, ctx.author.id))
			await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Enabled anti-mention-spam, banning users who exceed **{count}** mentions.\nLogging actions to: {channel.mention}')
		elif check and count:
			self.has_ms.invalidate(self, ctx.guild.id)

			await self.cursor.execute(f"UPDATE `mention_spam` SET count={count}{', channel=%s' % (channel.id) if channel else ''} WHERE guild={ctx.guild.id}")
			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Updated mention-spam threshold to **{count}**{' and action log channel to %s' % (channel.mention) if channel else '.'}")
		elif check and not count:
			user = await self.find_member(ctx.message, check['user'])
			channel = self.get_channel(ctx.guild, check['channel'])
			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} **Anti-Mention-Spam Options**\nThreshold (Mentions before ban): {check['count']}\nAction Log: {channel.mention}\nEnabler: `{user}`\nEnabled: __{check['time'].strftime('%m/%d/%Y %H:%M:%S')}__")
		else:
			await ctx.send('\N{NO ENTRY} Anti-Mention-Spam not enabled on guild.')

	async def remove_ms(self, guild):
		self.has_ms.invalidate(self, guild)

		await self.cursor.execute(f'DELETE FROM `mention_spam` WHERE guild={guild}')

	@mentionspam.command(name='off', aliases=['disable'])
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def mentionspam_off(self, ctx):
		q = await self.cursor.execute(f'SELECT channel FROM `mention_spam` WHERE guild={ctx.guild.id}')
		check = await q.fetchone()
		if not check:
			return await ctx.send('\N{NO ENTRY} Anti-Mention-Spam not enabled on guild.')
		await self.remove_ms(ctx.guild.id)
		await ctx.send('\N{NEGATIVE SQUARED CROSS MARK} Disabled mention-spam banning.')

	@mentionspam.command(name='channel')
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def mentionspam_channel(self, ctx, channel:discord.TextChannel=None):
		if not channel:
			channel = ctx.channel
		q = await self.cursor.execute(f'SELECT channel FROM `mention_spam` WHERE guild={ctx.guild.id}')
		check = await q.fetchone()
		if not check:
			await ctx.send('\N{NO ENTRY} Anti-Mention-Spam not enabled on guild.')
		elif check['channel'] == channel.id:
			await ctx.send('\N{WARNING SIGN} You cannot update the action log channel to the current one!')
		else:
			self.has_ms.invalidate(self, ctx.guild.id)

			await self.cursor.execute(f'UPDATE `mention_spam` SET channel={channel.id} WHERE guild={ctx.guild.id}')
			await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Updated mention-spam action log channel to: {channel.mention}')

	@cache.cache()
	async def has_raid(self, guild):
		q = await self.cursor.execute(f'SELECT channel,mode FROM `raids` WHERE guild={guild}')
		return await q.fetchone()

	async def check_raid(self, guild, channel, member, timestamp):
		check = await self.has_raid(guild.id)
		if not check:
			return
		elif check['mode'] != 2:
			return
		joined = member.joined_at
		# why discord
		if joined is None:
			return
		delta  = (joined - member.created_at).total_seconds() // 60
		if delta > 30:
			return
		delta = (timestamp - joined).total_seconds() // 60
		if delta > 30:
			return

		msg = f"Hello, guild `{guild}` has enabled strict raid protection mode, " \
		"your account did not pass the checks in place.\n" \
		"Please rejoin within a few hours when everything is better!"
		try:
			await member.send(msg)
		except discord.Forbidden:
			pass

		try:
			await member.kick(reason='Strict Raid Mode')
		except discord.Forbidden:
			if len(member.roles) == 1:
				return await self.remove_raid(guild.id)
		else:
			self.punished[guild.id].add(member.id)
			channel = self.get_channel(guild, check['channel'])
			try:
				assert channel
				await channel.send('\N{INFORMATION SOURCE} **Raid Action Log (Strict Mode)**\nKicked `{0} <{0.id}>`.'.format(member))
			except (AssertionError, discord.Forbidden):
				await self.remove_raid(guild.id)

	@cache.cache()
	async def has_ms(self, guild):
		q = await self.cursor.execute(f'SELECT channel,count FROM `mention_spam` WHERE guild={guild}')
		return await q.fetchone()

	@commands.Cog.listener()
	async def on_message(self, message):
		guild = message.guild
		if guild is None:
			return
		author = message.author
		if not isinstance(author, discord.Member):
			return
		elif author.id in self.punished:
			return
		elif author.id in (self.bot.user.id, self.bot.owner_id):
				return
		elif message.channel.permissions_for(author).administrator:
			return

		await self.check_raid(guild, message.channel, author, message.created_at)

		mentions = message.mentions
		if len(mentions) <= 3:
			return
		if mentions:
			mentions = [x for x in mentions if not x.bot and x.id != author.id]
		check = await self.has_ms(guild.id)
		if not check:
			return
		threshold = int(check['count'])
		if len(mentions) < threshold:
			return
		count = f"(**{len(mentions)}**/{threshold})"
		try:
			await author.ban(reason=f'Mention Spam {count}')
		except:
			pass
		else:
			try:
				channel = self.get_channel(guild, check['channel'])
				assert channel
				await channel.send(f'\N{INFORMATION SOURCE} **Anti-Mention-Spam Log**\nBanned `{author}` for exceeding mention threshold {count}.')
			except (AssertionError, discord.Forbidden, discord.NotFound):
				await self.remove_ms(guild.id)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		check = await self.has_raid(member.guild.id)
		if not check:
			return
		now = datetime.datetime.utcnow()
		created = (now - member.created_at).total_seconds() // 60
		was_kicked = False
		if check['mode'] == 2:
			was_kicked = self.punished.get(member.guild.id)
			if was_kicked is not None:
				try:
					was_kicked.remove(member.id)
				except KeyError:
					pass
				else:
					was_kicked = True
		if was_kicked:
			title = 'Member Re-Joined'
			colour = 0xdd5f53 # red
		else:
			title = 'Member Joined'
			colour = 0x53dda4 # green
			if created < 30:
				colour = 0xdda453 # yellow
		e = discord.Embed(title=title, colour=colour)
		e.timestamp = now
		e.set_footer(text='Created')
		e.set_author(name=str(member), icon_url=member.avatar_url or member.default_avatar_url)
		e.add_field(name='ID', value=member.id)
		e.add_field(name='Joined', value=member.joined_at)
		e.add_field(name='Created', value=human_timedelta(member.created_at))
		try:
			channel = member.guild.get_channel(check['channel'])
			assert channel
			await channel.send(embed=e)
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_raid(member.guild.id)


def setup(bot):
	bot.add_cog(Raids(bot))
