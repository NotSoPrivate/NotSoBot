import datetime
import time
from collections import deque

import discord
from discord.ext import commands
from mods.cog import Cog
from utils import cache, checks

cool = "```xl\n{0}\n```"

class Logs(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.discord_path = bot.path.discord
		self.files_path = bot.path.files
		self.bytes_download = bot.bytes_download
		self.truncate = bot.funcs.truncate
		self.merge_images = bot.funcs.merge_images
		self.banned_members = deque(maxlen=10)

	async def remove_guild(self, guild):
		sql = f"DELETE FROM `logs` WHERE guild={guild}"
		await self.cursor.execute(sql)

	# async def remove_guild_tracking(self, guild):
	# 	sql = f"DELETE FROM `tracking` WHERE guild={guild}"
	# 	await self.cursor.execute(sql)

	@commands.group(aliases=['slogs', 'adminlogs'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def serverlogs(self, ctx, channel:discord.TextChannel=None):
		"""Setup Guild Logs for a Specific Channel or Current Channel"""
		chan = channel or ctx.channel
		check = "SELECT channel FROM `logs` WHERE guild={0}".format(ctx.guild.id)
		q = await self.cursor.execute(check)
		result = await q.fetchone()
		if not result:
			sql = "INSERT INTO `logs` (`guild`, `channel`) VALUES (%s, %s)"
			await self.cursor.execute(sql, (ctx.guild.id, chan.id))
			await ctx.send("\N{WHITE HEAVY CHECK MARK} Set Guild Logs to {0.mention}".format(chan))
		elif result['channel'] == chan.id:
			remove_sql = "DELETE FROM `logs` WHERE guild={0}".format(ctx.guild.id)
			await self.cursor.execute(remove_sql)
			await ctx.send(":negative_squared_cross_mark: Disabled Guild Logs.")
		else:
			update_sql = "UPDATE `logs` SET channel={0} WHERE guild={1}".format(chan.id, ctx.guild.id)
			await self.cursor.execute(update_sql)
			await ctx.send("\N{WHITE HEAVY CHECK MARK} Updated Guild Logs to {0.mention}".format(chan))

		self.has_log.invalidate(self, ctx.guild.id)

	@serverlogs.command(name='disable', aliases=['off', 'clear', 'deactivate'])
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def serverlogs_disable(self, ctx):
		check = "SELECT channel FROM `logs` WHERE guild={0}"
		check = check.format(ctx.guild.id)
		q = await self.cursor.execute(check)
		result = await q.fetchall()
		if result:
			remove_sql = "DELETE FROM `logs` WHERE guild={0}"
			remove_sql = remove_sql.format(ctx.guild.id)
			await self.cursor.execute(remove_sql)
			await ctx.send(":negative_squared_cross_mark: Disabled Guild Logs.")

			self.has_log.invalidate(self, ctx.guild.id)
		else:
			await ctx.send('\N{NO ENTRY} Guild does not have logs enabled!')

	@serverlogs.group(name='ignore', invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def serverlogs_ignore(self, ctx, *users:discord.User):
		if not users:
			return await ctx.send('\N{NO ENTRY} Please input user mention(s) or id(s).')
		users = list(users)[:5]
		guild = ctx.guild.id
		q = await self.cursor.execute(f'SELECT guild FROM `logs` WHERE guild={guild}')
		if not await q.fetchone():
			return await ctx.send('\N{NO ENTRY} Guild does not have logs enabled.')
		q = await self.cursor.execute(f'SELECT * FROM `logs_ignore` WHERE guild={guild}')
		result = await q.fetchall()
		if result:
			ids = [x['id'] for x in result]
			for u in users:
				if u.id in ids:
					ids.remove(u.id)
					await self.cursor.execute('DELETE FROM `logs_ignore` WHERE guild=%s AND id=%s', (guild, u.id))
					await ctx.send(':negative_squared_cross_mark: Removed `{0}` from guild log ignore.'.format(u))
					users.remove(u)
					self.is_ignored.invalidate(self, guild, u)
					if users:
						continue
					return
		sql = 'REPLACE INTO `logs_ignore` (`guild`, `id`) VALUES (%s, %s)'
		for u in users:
			await self.cursor.execute(sql, (guild, u.id))
			self.is_ignored.invalidate(self, guild, u)
		await ctx.send('\N{WHITE HEAVY CHECK MARK} Ignoring `{0}` from guild log.'.format(', '.join([str(x) for x in users])))
	
	# @serverlogs_ignore.command(name='avatar')
	# @commands.guild_only()
	# @checks.admin_or_perm(manage_guild=True)
	# async def serverlogs_ignore_avatar(self, ctx, *users:discord.User):
	# 	if not len(users):
	# 		return await ctx.send('\N{NO ENTRY} Please input user mention(s) or id(s).')
	# 	users = list(users)
	# 	guild = ctx.guild.id
	# 	q = await self.cursor.execute(f'SELECT guild FROM `logs` WHERE guild={guild}')
	# 	result = await q.fetchone()
	# 	if not result:
	# 		return await ctx.send('\N{NO ENTRY} Guild does not have logs enabled.')
	# 	q = await self.cursor.execute(f'SELECT * FROM `logs_ignore` WHERE guild={guild} AND type=1')
	# 	result = await q.fetchall()
	# 	if result:
	# 		ids = [x['id'] for x in result]
	# 		for u in users:
	# 			if u.id in ids:
	# 				ids.remove(u.id)
	# 				await self.cursor.execute('DELETE FROM `logs_ignore` WHERE type=1 AND guild=%s AND id=%s', (guild, u.id))
	# 				await ctx.send(':negative_squared_cross_mark: Removed `{0}` from avatar ignore.'.format(u))
	# 				users.remove(u)
	# 				if len(users):
	# 					continue
	# 				return
	# 	sql = 'INSERT INTO `logs_ignore` (`type`, `guild`, `id`) VALUES (%s, %s, %s)'
	# 	for user in users:
	# 		await self.cursor.execute(sql, (1, guild, user.id))
	# 	await ctx.send('\N{WHITE HEAVY CHECK MARK} Ignoring `{0}` from avatar log.'.format(', '.join([str(x) for x in users])))

	# @serverlogs_ignore.group(name='global', invoke_without_command=True)
	# @commands.guild_only()
	# @commands.is_owner()
	# async def serverlogs_ignore_global(self, ctx, *users:discord.User):
	# 	if not len(users):
	# 		return await ctx.send('\N{NO ENTRY} Please input user mention(s) or id(s).')
	# 	users = list(users)
	# 	sql = 'SELECT * FROM `global_log_ignore` WHERE user={0} AND NOT avatar'
	# 	for user in users:
	# 		q = await self.cursor.execute(sql.format(user.id))
	# 		result = await q.fetchall()
	# 		if result:
	# 			sql = 'DELETE FROM `global_log_ignore` WHERE user={0} AND NOT avatar'
	# 			sql = sql.format(user.id)
	# 			await self.cursor.execute(sql)
	# 			await ctx.send(':negative_squared_cross_mark: Removed `{0}` from global log ignore.'.format(user))
	# 		else:
	# 			sql = 'INSERT INTO `global_log_ignore` (`user`) VALUES (%s)'
	# 			await self.cursor.execute(sql, (user.id))
	# 			await ctx.send('\N{WHITE HEAVY CHECK MARK} Added `{0}` to global log ignore.'.format(user))

	# @serverlogs_ignore_global.command(name='avatar')
	# @commands.guild_only()
	# @commands.is_owner()
	# async def serverlogs_ignore_global_avatar(self, ctx, *users:discord.User):
	# 	if not len(users):
	# 		return await ctx.send('\N{NO ENTRY} Please input user mention(s) or id(s).')
	# 	users = list(users)
	# 	sql = 'SELECT * FROM `global_log_ignore` WHERE user={0} AND avatar'
	# 	for user in users:
	# 		q = await self.cursor.execute(sql.format(user.id))
	# 		result = await q.fetchall()
	# 		if result:
	# 			sql = 'DELETE FROM `global_log_ignore` WHERE user={0} AND avatar'
	# 			sql = sql.format(user.id)
	# 			await self.cursor.execute(sql)
	# 			await ctx.send(':negative_squared_cross_mark: Removed `{0}` from global avatar log ignore.'.format(user))
	# 		else:
	# 			sql = 'INSERT INTO `global_log_ignore` (`user`, `avatar`) VALUES (%s, %s)'
	# 			await self.cursor.execute(sql, (user.id, 1))
	# 			await ctx.send('\N{WHITE HEAVY CHECK MARK} Added `{0}` to global avatar log ignore.'.format(user))

	# @commands.group(invoke_without_command=True, aliases=['messagetracking', 'trackmessage'])
	# @commands.guild_only()
	# @checks.admin_or_perm(manage_guild=True)
	# async def track(self, ctx, *, txt:str):
	# 	"""Track messages in your guild"""
	# 	if len(txt) > 1500:
	# 		return await ctx.send("\N{NO ENTRY} `Text too long (<= 1500)`")
	# 	chan = ctx.channel
	# 	sql = "SELECT channel FROM `tracking` WHERE guild={0} LIMIT 1".format(ctx.guild.id)
	# 	q = await self.cursor.execute(sql)
	# 	s_result = await q.fetchone()
	# 	check = "SELECT txt FROM `tracking` WHERE guild=%s AND txt=%s LIMIT 1"
	# 	q = await self.cursor.execute(check, (ctx.guild.id, txt))
	# 	result = await q.fetchone()
	# 	if not result or result['txt'] != txt:
	# 		sql = "INSERT INTO `tracking` (`txt`, `guild`, `channel`) VALUES (%s, %s, %s)"
	# 		if s_result:
	# 			await self.cursor.execute(sql, (txt, ctx.guild.id, s_result['channel']))
	# 			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Added \"{txt}\" to tracking.")
	# 		else:
	# 			await self.cursor.execute(sql, (txt, ctx.guild.id, chan.id))
	# 			await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Set channel to track all messages with \"{txt}\"\nRun the `track log` command to change channel it logs in.")
	# 	else:
	# 		await ctx.send("\N{NO ENTRY} `Tracking for text \"{0}\" already exists!`\nRemove using the remove command.".format(txt))

	# @track.command(name='channel')
	# @commands.guild_only()
	# @checks.admin_or_perm(manage_guild=True)
	# async def track_channel(self, ctx, *channels:discord.TextChannel):
	# 	check = 'SELECT id FROM `tracking` WHERE guild={0}'.format(ctx.guild.id)
	# 	q = await self.cursor.execute(check)
	# 	result = await q.fetchall()
	# 	if not result:
	# 		return await ctx.send("\N{NO ENTRY} `This guild is not tracking any messages!`")
	# 	if not len(channels):
	# 		channels = [ctx.channel]
	# 	first = True
	# 	removed = []
	# 	added = []
	# 	sql = 'SELECT channel FROM `tracking_channels` WHERE guild={0}'.format(ctx.guild.id)
	# 	q = await self.cursor.execute(sql)
	# 	tracked_channels = [x['channel'] for x in await q.fetchall()]
	# 	if tracked_channels:
	# 		first = False
	# 	for channel in channels:
	# 		if channel.id in tracked_channels:
	# 			sql = 'DELETE FROM `tracking_channels` WHERE channel={0}'.format(channel.id)
	# 			await self.cursor.execute(sql)
	# 			removed.append(channel)
	# 		else:
	# 			sql = 'INSERT INTO `tracking_channels` (`guild`, `channel`) VALUES (%s, %s)'
	# 			await self.cursor.execute(sql, (ctx.guild.id, channel.id))
	# 			added.append(channel)
	# 	if len(removed):
	# 		await ctx.send(':negative_squared_cross_mark: Removed "{0}" from tracked channels.'.format(', '.join([x.mention for x in removed])))
	# 	if len(added):
	# 		if first:
	# 			await ctx.send('\N{WHITE HEAVY CHECK MARK} Tracking only "{0}" now.'.format(', '.join([x.mention for x in added])))
	# 		else:
	# 			await ctx.send('\N{WHITE HEAVY CHECK MARK} Added "{0}" to tracked channels.'.format(', '.join([x.mention for x in added])))

	# @track.command(name='log')
	# @commands.guild_only()
	# @checks.admin_or_perm(manage_guild=True)
	# async def track_log(self, ctx, chan:discord.TextChannel=None):
	# 	if chan is None:
	# 		chan = ctx.channel
	# 	update_sql = 'UPDATE `tracking` SET channel={0} WHERE guild={1}'
	# 	update_sql = update_sql.format(chan.id, ctx.guild.id)
	# 	check = 'SELECT channel FROM `tracking` WHERE guild={0} LIMIT 1'.format(ctx.guild.id)
	# 	q = await self.cursor.execute(check)
	# 	result = await q.fetchone()
	# 	if not result:
	# 		await ctx.send("\N{NO ENTRY} `This guild is not tracking any messages!`")
	# 	elif result['channel'] == chan.id:
	# 		await ctx.send("\N{NO ENTRY} `Channel is already the tracking logs channel!`\nUse the remove all command to stop tracking.")
	# 	else:
	# 		await self.cursor.execute(update_sql)
	# 		await ctx.send("\N{WHITE HEAVY CHECK MARK} Updated text tracking channel to {0}".format(chan.mention))

	# @track.group(name='remove', invoke_without_command=True)
	# @commands.guild_only()
	# @checks.admin_or_perm(manage_guild=True)
	# async def track_remove(self, ctx, *, txt:str):
	# 	remove_sql = "DELETE FROM `tracking` WHERE guild=%s AND txt=%s"
	# 	check = "SELECT guild FROM `tracking` WHERE guild=%s AND txt=%s LIMIT 1"
	# 	args = (ctx.guild.id, txt)
	# 	q = await self.cursor.execute(check, args)
	# 	result = await q.fetchone()
	# 	if not result:
	# 		await ctx.send("\N{NO ENTRY} `That text isn't being tracked!`")
	# 	else:
	# 		await self.cursor.execute(remove_sql, args)
	# 		await ctx.send("\N{CROSS MARK} Removed text from tracking.")

	# @track_remove.command(name='all')
	# @commands.guild_only()
	# @checks.admin_or_perm(manage_guild=True)
	# async def track_remove_all(self, ctx):
	# 	sql = "DELETE FROM `tracking` WHERE guild={0}".format(ctx.guild.id)
	# 	check = 'SELECT guild FROM `tracking` WHERE guild={0} LIMIT 1'.format(ctx.guild.id)
	# 	q = await self.cursor.execute(check)
	# 	result = await q.fetchone()
	# 	if not result:
	# 		await ctx.send("\N{NO ENTRY} `Guild has not added any text to be tracked!`")
	# 	else:
	# 		await self.cursor.execute(sql)
	# 		await ctx.send("\N{CROSS MARK} Reset/Removed all tracked text.")

	# @track.command(name='list')
	# @commands.guild_only()
	# @checks.admin_or_perm(manage_guild=True)
	# async def track_list(self, ctx):
	# 	sql = "SELECT txt FROM `tracking` WHERE guild={0}"
	# 	sql = sql.format(ctx.guild.id)
	# 	q = await self.cursor.execute(sql)
	# 	result = await q.fetchall()
	# 	if not result:
	# 		await ctx.send("\N{WARNING SIGN} `This guild does not have any text being tracked!`")
	# 	else:
	# 		results = ''
	# 		for s in result:
	# 			results += '`{0}`\n'.format(s['txt'])
	# 		await ctx.send('**All Tracked Text**\n'+results)

	@commands.command(aliases=['commanddelete', 'cmd_delete', 'command_delete', 'cmdelete'])
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def cmddelete(self, ctx):
		sql = 'SELECT * FROM `command_delete` WHERE guild={0}'.format(ctx.guild.id)
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if result:
			sql = 'DELETE FROM `command_delete` WHERE guild={0}'
			sql = sql.format(ctx.guild.id)
			await self.cursor.execute(sql)
			await ctx.send(':negative_squared_cross_mark: Disabled on command delete messages.')
		else:
			sql = 'INSERT INTO `command_delete` (`guild`) VALUES (%s)'
			await self.cursor.execute(sql, (ctx.guild.id,))
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Enabled on command delete messages.')

	@cache.cache(maxsize=1024)
	async def is_ignored(self, guild, user):
		# if kwargs.pop('tracking', False):
		# 	q = await self.cursor.execute(f'SELECT channel FROM `tracking_channels` WHERE guild={message.guild.id}')
		# 	result = await q.fetchall()
		# 	if not result:
		# 		return False
		# 	return not message.channel.id in [x['channel'] for x in result]

		if not isinstance(user, int):
			user = user.id

		q = await self.cursor.execute(f'SELECT id FROM `logs_ignore` WHERE guild={guild.id}')
		result = await q.fetchall()
		if not result:
			return False
		return user in (x['id'] for x in result)

		# q = await self.cursor.execute(f'SELECT avatar FROM `global_log_ignore` WHERE user={user} AND avatar=0')
		# result = await q.fetchone()
		# if result:
		# 	return True
		# elif kwargs.pop('global_only', False):
		# 	return False

	@cache.cache(maxsize=1024)
	async def has_log(self, guild):
		sql = "SELECT channel FROM `logs` WHERE guild={0}".format(guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		if not result:
			return False
		channel = guild.get_channel(result['channel'])
		assert channel
		return channel

	# Deleted command messages
	@commands.Cog.listener(name="on_message_delete")
	async def on_command_message_delete(self, message):
		if message.guild is None:
			return
		elif message.id not in self.bot.command_messages:
			return
		elif message.id in self.bot.pruned_messages:
			return
		# Prevent a user banned from > 1 servers from breaking
		# command logging
		mgid = message.author.id + message.guild.id
		if mgid in self.banned_members:
			return
		sql = f'SELECT * FROM `command_delete` WHERE guild={message.guild.id}'
		q = await self.cursor.execute(sql)
		check = await q.fetchall()
		if not check:
			return
		elif await self.is_ignored(message.guild, message.author):
			return
		elif message.created_at < datetime.datetime.utcnow() - datetime.timedelta(minutes=15):
			return
		command, prefix, = self.bot.command_messages[message.id][:2]
		await message.channel.send(f'\N{WARNING SIGN} `{message.author}` **deleted command message**: {prefix + command}')

	# @commands.Cog.listener()
	# async def on_message(self, message):
	# 	if message.author.bot:
	# 		return
	# 	elif message.guild is None:
	# 		return
	# 	elif await self.is_ignored(message, user=True):
	# 		return
	# 	if await self.is_ignored(message, tracking=True):
	# 		return
	# 	sql = "SELECT channel,txt FROM `tracking` WHERE guild={0}".format(message.guild.id)
	# 	q = await self.cursor.execute(sql)
	# 	result = await q.fetchall()
	# 	if not result:
	# 		return
	# 	channel = result[0]['channel']
	# 	if channel == message.channel.id:
	# 		return
	# 	channel = message.guild.get_channel(channel)
	# 	try:
	# 		assert channel
	# 		content = message.clean_content.lower()
	# 		for s in result:
	# 			txt = s['txt']
	# 			if txt.lower() in content:
	# 				msg = f"`[{time.strftime('%I:%M:%S %p')}]` \"{txt}\" was said **{content.count(txt.lower())}** times in {message.channel.mention} by **__{message.author}__**"
	# 				await channel.send(msg)
	# 	except (AssertionError, discord.Forbidden, discord.NotFound):
	# 		await self.remove_guild_tracking(message.guild.id)

	@commands.Cog.listener()
	async def on_command(self, ctx):
		try:
			if ctx.guild is None:
				return
			channel = await self.has_log(ctx.guild)
			if not channel:
				return
			elif await self.is_ignored(ctx.guild, ctx.author):
				return
			msg = "User: {0} <{1}>\n".format(ctx.author, ctx.author.id).replace("'", "")
			msg += "Command: {0}\n".format(ctx.invoked_with)
			msg2 = "`Channel:` {0}\n".format(ctx.channel.mention)
			msg2 += "`Context Message:` \"{0}\"".format(ctx.message.content)
			msg = f"`[{time.strftime('%I:%M:%S %p')}]`\N{HEAVY EXCLAMATION MARK SYMBOL} **Command Log**\n{cool.format(msg)}{msg2}"
			await channel.send(msg[:2000])
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_guild(ctx.guild.id)

	@commands.Cog.listener()
	async def on_raw_message_delete(self, payload):
		message = payload.cached_message
		try:
			files = None
			if payload.guild_id is None:
				return

			if message and message.author == self.bot.user:
				return
			guild = self.bot.get_guild(payload.guild_id)
			channel = await self.has_log(guild)
			if not channel:
				return
			elif payload.channel_id == channel.id:
				return
			elif message and await self.is_ignored(message.guild, message.author):
				return
			elif payload.message_id in self.bot.pruned_messages:
				return

			if message is None:
				msg = f"Message ID: {payload.message_id}"
				msg2 = f"Channel: <#{payload.channel_id}>\n"
				msg = cool.format(msg)
				final = "`[{0}]` \N{WASTEBASKET} **Raw Message Delete Log**\n".format(time.strftime("%I:%M:%S %p")) \
								+ msg + msg2
				return await channel.send(final)

			msg = "User: {0} <{1}>\n".format(message.author, message.author.id).replace("'", "")
			msg2 = "Channel: {0}\n".format(message.channel.mention)
			if message.content != "":
				msg2 += "`Deleted Message:` \"{0}\"".format(message.clean_content)
			final = "`[{0}]` \N{WASTEBASKET} **Message Delete Log**\n".format(time.strftime("%I:%M:%S %p")) \
							+ cool.format(msg) + msg2
			if message.attachments:
				ac = []
				for x in message.attachments:
					ac.append((
						await self.bytes_download(x.proxy_url), x.filename
					))
				#discord.File should auto close the BytesIO objects on return
				files = [discord.File(b[0], b[1]) for b in ac if b[0]]
			await self.truncate(channel, final, embeds=message.embeds, files=files)
		except discord.HTTPException:
			pass
		except (AssertionError, discord.Forbidden, discord.NotFound):
			if message is None and payload.guild_id:
				await self.remove_guild(payload.guild_id)
			else:
				await self.remove_guild(message.guild.id)

	@commands.Cog.listener()
	async def on_message_edit(self, before, after):
		try:
			if before.guild is None:
				return
			elif before.content == after.content:
				return
			elif before.author == self.bot.user:
				return
			channel = await self.has_log(before.guild)
			if not channel:
				return
			if before.channel.id == channel.id:
				return
			if await self.is_ignored(before.guild, before.author):
				return
			msg = "User: {0} <{1}>\n".format(after.author.name, after.author.id).replace("'", "")
			msg2 = "Channel: {0}\n".format(after.channel.mention)
			msg2 += "`Before:` \"{0}\"\n".format(before.clean_content)
			msg2 += "`After:` \"{0}\"".format(after.clean_content)
			await self.truncate(
				channel,
				"`[{0}]` :pencil2: **Message Edit Log**\n".format(time.strftime("%I:%M:%S %p")) + cool.format(msg) + msg2,
				embeds=after.embeds
			)
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_guild(after.guild.id)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		try:
			if member == self.bot.user:
				return
			channel = await self.has_log(member.guild)
			if not channel:
				return
			if await self.is_ignored(member.guild, member):
				return
			msg = "Member Joined: {0.name} <{0.id}>\n".format(member)
			msg += "Guild: {0.name} <{0.id}>\n".format(member.guild).replace("'", "")
			await channel.send("`[{0}]` :inbox_tray: **Member Join Log**\n".format(time.strftime("%I:%M:%S %p"))+cool.format(msg))
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_guild(member.guild.id)

	@commands.Cog.listener()
	async def on_member_ban(self, guild, user):
		self.banned_members.append(user.id + guild.id)

	@commands.Cog.listener()
	async def on_member_remove(self, member):
		try:
			if member == self.bot.user:
				return
			channel = await self.has_log(member.guild)
			if not channel:
				return
			if await self.is_ignored(member.guild, member):
				return
			msg = "User: {0.name} <{0.id}>\n".format(member)
			await channel.send("`[{0}]` :outbox_tray: **Member Leave Log**\n".format(time.strftime("%I:%M:%S %p"))+cool.format(msg))
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_guild(member.guild.id)

	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		try:
			if before == self.bot.user:
				return
			elif before.avatar == after.avatar and before.name == after.name:
				return
			channel = await self.has_log(before.guild)
			if not channel:
				return
			elif await self.is_ignored(before.guild, before):
				return
			# elif before.avatar != after.avatar:
			# 	if not await self.is_ignored(None, avatar=True, guild=before.guild, u=before):
			# 		msg = "User: {0} <{0.id}>\n".format(after)
			# 		if before.avatar:
			# 			before_avatar = await self.bytes_download(str(before.avatar_url_as(format='png')))
			# 		after_avatar = await self.bytes_download(str(after.avatar_url_as(format='png')))
			# 		if not after_avatar:
			# 			return
			# 		elif before.avatar is None:
			# 			return await channel.send(file=after_avatar, filename='new_avatar.png', content=":frame_photo: **New Avatar Log**\n"+cool.format(msg))
			# 		elif not before_avatar:
			# 			return
			# 		final = await self.merge_images([before_avatar, after_avatar], method=2)
			# 		if final and not final.closed:
			# 			return await channel.send(file=final, filename='avatar_change.png', content="`[{0}]` :frame_photo: **Avatar Change Log**\n".format(time.strftime("%I:%M:%S %p"))+cool.format(msg))
			elif before.name != after.name:
				msg = "User Name Before: {0.name} <{0.id}>\n".format(before)
				msg += "User Name After: {0.name}\n".format(after)
				await channel.send("`[{0}]` :name_badge: **Name Change Log**\n".format(time.strftime("%I:%M:%S %p"))+cool.format(msg))
		except discord.HTTPException:
			pass
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_guild(after.guild.id)

	# @commands.Cog.listener()
	# async def on_guild_update(self, before, after):
	# 	try:
	# 		channel = await self.has_log(before)
	# 		if not channel:
	# 			return
	# 		if before.icon != after.icon:
	# 			msg = "Guild: {0.name} <{0.id}>\n".format(after)
	# 			#dl it FAST
	# 			if before.icon:
	# 				before_icon = await self.bytes_download(before.icon_url)
	# 			after_icon = await self.bytes_download(after.icon_url)
	# 			if not after_icon:
	# 				return
	# 			if before.icon is None:
	# 				return await channel.send(file=after_icon, filename='new_guild_icon.png', content="`[{0}]` :frame_photo: **New Guild Icon Log**\n".format(time.strftime("%I:%M:%S %p"))+cool.format(msg))
	# 			if not before_icon:
	# 				return
	# 			final = await self.merge_images([before_icon, after_icon], method=2)
	# 			await channel.send(file=final, filename='guild_icon_change.png', content="`[{0}]` :frame_photo: **Guild Icon Change Log**\n".format(time.strftime("%I:%M:%S %p"))+cool.format(msg))
	# 	except (AssertionError, discord.Forbidden, discord.NotFound):
	# 		await self.remove_guild(after.id)

	@commands.Cog.listener()
	async def on_voice_state_update(self, member, before, after):
		try:
			if not member or not member.guild:
				return
			guild = member.guild
			channel = await self.has_log(guild)
			if not channel:
				return
			check = await self.is_ignored(guild, member)
			if check:
				return
			if before.channel != after.channel:
				if isinstance(member, int):
					try:
						member = await guild.fetch_member(member)
					except discord.NotFound:
						return # damn rude
				msg = "User: {0} <{0.id}>\n".format(member)
				if not before.channel and after.channel:
					msg += "Voice Channel Join: {0.name} <{0.id}>".format(after.channel)
				elif before.channel and after.channel:
					msg += "Voice Channel Before: {0.name} <{0.id}>\n".format(before.channel)
					msg += "Voice Channel After: {0.name} <{0.id}>".format(after.channel)
				elif before.channel and not after.channel:
					msg += "Voice Channel Leave: {0.name} <{0.id}>".format(before.channel)
				await channel.send("`[{0}]` :bangbang: **Voice Channel Log**\n".format(time.strftime("%I:%M:%S %p"))+cool.format(msg))
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_guild(guild.id)

def setup(bot):
	if not bot.self_bot:
		mod = Logs(bot)
		bot.add_cog(mod)
