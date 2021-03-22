import asyncio
import datetime
from copy import copy
from io import BytesIO

import discord
from discord.embeds import EmbedProxy, _EmptyEmbed
from discord.ext import commands
from discord.ext.commands.converter import MemberOrInt

from mods.cog import Cog
from utils import cache, checks
from utils.funcs import get_prefix
from utils.paginator import CannotPaginate, Pages


class Moderation(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.discord_path = bot.path.discord
		self.files_path = bot.path.files
		self.nick_massing = {}
		self.nick_unmassing = {}
		self.format_time = bot.funcs.format_time
		self.find_member = bot.funcs.find_member
		self.is_off = bot.funcs.is_off
		self.query_blacklist = bot.funcs.query_blacklist

	@commands.command()
	@commands.cooldown(2, 5)
	@checks.mod_or_perm(manage_messages=True)
	async def clean(self, ctx, max_messages:int=None):
		"""Removes inputed amount of bot and invoker messages."""
		none = False
		if max_messages is None:
			none = True
			max_messages = 50
		if max_messages and max_messages > 2000:
			return await ctx.send("2 many messages (<= 2000)")
		guild = ctx.guild
		channel = ctx.channel
		me = guild.me if guild else self.bot.user
		perms = guild.me.permissions_in(channel).manage_messages if guild else False
		kwargs = {
			'limit': max_messages,
			'before': ctx.message,
			'after': datetime.datetime.utcnow() - datetime.timedelta(minutes=10) if none else None,
		}
		if guild and perms and not self.bot.self_bot:
			prefix = (await get_prefix(self.bot, ctx.message))[0]
			check = lambda m: m.author == me or any(map(m.content.startswith, prefix))
			deleted = await ctx.purge(check=check, **kwargs)
		elif not perms:
			check = lambda m: m.author == me
			if ctx.guild is None:
				deleted = []
				async for m in channel.history(**kwargs):
					if check(m):
						await ctx.delete(m)
						deleted.append(m)
			else:
				deleted = await ctx.purge(bulk=False, check=check, **kwargs)
		x = await ctx.send(f"Removed `{len(deleted)}` messages out of `{max_messages}` searched messages")
		await asyncio.sleep(6)
		try:
			await ctx.delete(ctx.message, x)
		except:
			pass

	@commands.group(invoke_without_command=True, aliases=['purge', 'deletemessages'])
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def prune(self, ctx, *max_messages:MemberOrInt):
		"""Delete inputed amount of messages in a channel."""
		check = None
		if max_messages:
			users = [x.id for x in max_messages if isinstance(x, discord.abc.User)]
			max_messages = [x for x in max_messages if isinstance(x, int)][0] if any(isinstance(x, int) for x in max_messages) else 50
			if max_messages > 6000:
				return await ctx.send("2 many messages (<= 6000)")
			if users:
				check = lambda m: m.author.id in users
		deleted = await ctx.purge(limit=max_messages or 50, before=ctx.message, check=check,
															after=datetime.datetime.utcnow() - datetime.timedelta(minutes=5) if not max_messages else None)
		users = set([str(u.author) for u in deleted])
		if users and not deleted:
			x = await ctx.send("\N{WARNING SIGN} No messages found by `{0}` within `{1}` searched messages!".format(', '.join(users), max_messages))
		elif not max_messages and not deleted:
			x = await ctx.send('\N{WARNING SIGN} `No messages found within the last 5 minutes.`')
		elif not deleted:
			x = await ctx.send('\N{WARNING SIGN} `No messages pruned.`')
		else:
			x = await ctx.send("ok, removed **{0}** messages by `{1}`.".format(len(deleted), ', '.join(users)))
		await asyncio.sleep(6)
		try:
			await ctx.delete(x, ctx.message)
		except:
			pass

	@prune.command(name='bots')
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def prune_bots(self, ctx, max_messages:int=50):
		if max_messages > 5000 or max_messages < 1:
			return await ctx.send("2 many messages (<= 5000)")
		deleted = await ctx.purge(limit=max_messages, before=ctx.message, check=lambda m: m.author.bot)
		if not deleted:
			x = await ctx.send("\N{WARNING SIGN} No messages found by bots within `{0}` searched messages!".format(max_messages))
		else:
			users = set([str(u.author) for u in deleted])
			x = await ctx.send('ok, removed `{0}` messages by bot{2} `{1}`.'.format(len(deleted), ', '.join(users), 's' if len(users) > 1 else ''))
		await asyncio.sleep(6)
		await ctx.delete(ctx.message, x, error=False)

	@prune.command(name='attachments', aliases=['files'])
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def prune_attachments(self, ctx, max_messages:int=50):
		if max_messages > 5000 or max_messages < 1:
			return await ctx.send("2 many messages (<= 5000)")
		deleted = await ctx.purge(limit=max_messages, before=ctx.message, check=lambda m: len(m.attachments))
		if not deleted:
			x = await ctx.send("\N{WARNING SIGN} No messages found with attachments within `{0}` searched messages!".format(max_messages))
		else:
			users = set([str(u.author) for u in deleted])
			x = await ctx.send('ok, removed `{0}` messages with attachments by `{1}`.'.format(len(deleted), ', '.join(users)))
		await asyncio.sleep(6)
		await ctx.delete(ctx.message, x, error=False)

	@prune.command(name='embeds')
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def prune_embeds(self, ctx, max_messages:int=50):
		if max_messages > 5000 or max_messages < 1:
			return await ctx.send("2 many messages (<= 5000)")
		deleted = await ctx.purge(limit=max_messages, before=ctx.message, check=lambda m: len(m.embeds))
		if not deleted:
			x = await ctx.send("\N{WARNING SIGN} No messages found with embeds within `{0}` searched messages!".format(max_messages))
		else:
			users = set([str(u.author) for u in deleted])
			x = await ctx.send('ok, removed `{0}` messages with embeds by `{1}`.'.format(len(deleted), ', '.join(users)))
		await asyncio.sleep(6)
		await ctx.delete(ctx.message, x, error=False)

	@prune.command(name='images')
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def prune_images(self, ctx, max_messages:int=50):
		if max_messages > 5000 or max_messages < 1:
			return await ctx.send("2 many messages (<= 5000)")
		deleted = await ctx.purge(limit=max_messages, before=ctx.message, check=lambda m: len(m.attachments) or len(m.embeds))
		if not deleted:
			x = await ctx.send("\N{WARNING SIGN} No messages found with images within `{0}` searched messages!".format(max_messages))
		else:
			users = set([str(u.author) for u in deleted])
			x = await ctx.send('ok, removed `{0}` messages with images by `{1}`.'.format(len(deleted), ', '.join(users)))
		await asyncio.sleep(6)
		await ctx.delete(ctx.message, x, error=False)

	@prune.command(name='with', aliases=['contains', 'content'])
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def prune_with(self, ctx, *, max_messages:str):
		txt = max_messages
		for s in max_messages.split():
			if s.isdigit():
				max_messages = int(s)
				txt = txt.replace(str(max_messages), '')
				break
		txt = txt.strip()
		if not txt:
			return await ctx.send('\N{NO ENTRY} `Please input a string to search for in messages and delete.`')
		if not max_messages or isinstance(max_messages, str):
			max_messages = 100
		if max_messages > 5000 or max_messages < 1:
			return await ctx.send("2 many messages (<= 5000)")
		def check(m):
			if txt in m.clean_content:
				return True
			for e in m.embeds:
				for f in e.fields:
					if txt in f.name or txt in f.value:
						return True
				content = (e.title, e.description, e.footer)
				if any(txt in x for x in content if not isinstance(x, (EmbedProxy, _EmptyEmbed))):
					return True
		deleted = await ctx.purge(limit=max_messages, before=ctx.message, check=check)
		if not deleted:
			x = await ctx.send("\N{WARNING SIGN} No messages found with given string within `{0}` searched messages!".format(max_messages))
		else:
			users = set([str(u.author) for u in deleted])
			x = await ctx.send('ok, removed `{0}` messages with a string by `{1}`.'.format(len(deleted), ', '.join(users)))
		await asyncio.sleep(6)
		await ctx.delete(ctx.message, x, error=False)

	@prune.command(name='to', aliases=['after'])
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def prune_to(self, ctx, message_id:int, channel:discord.TextChannel=None):
		if not channel:
			channel = ctx.channel
		try:
			msg = await ctx.channel.fetch_message(message_id)
		except:
			await ctx.send('\N{WARNING SIGN} `Message ID not found in channel.`')
		else:
			deleted = await ctx.purge(limit=5000, after=msg)
			if not deleted:
				x = await ctx.send("\N{WARNING SIGN} `No messages found after given message id!`")
			else:
				users = set([str(u.author) for u in deleted])
				x = await ctx.send('ok, removed `{0}` messages after message id by `{1}`.'.format(len(deleted), ', '.join(users)))
			await asyncio.sleep(6)
			await ctx.delete(ctx.message, x, error=False)

	@commands.group(invoke_without_command=True, aliases=['unblacklist', 'ignore'])
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def blacklist(self, ctx, *, user:discord.User=None):
		"""Blacklist/Unblacklist user from guild"""
		if user is None:
			return await ctx.send("**Blacklist Base Command**\nCommands:\n`global`: Owner Only\n`user`: Guild admin (manage_guild) only\n`channel`: Guild admin (manage_guild) only\n Call once to blacklist, again to unblacklist.")
		if user == ctx.author:
			return await ctx.send('lol dumbass')
		elif await self.bot.is_owner(user):
			return await ctx.send('how about you fuck off')
		sql = 'SELECT * FROM `blacklist` WHERE guild={0} AND user={1}'
		sql = sql.format(ctx.guild.id, user.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			sql = 'INSERT INTO `blacklist` (`guild`, `user`, `admin`) VALUES (%s, %s, %s)'
			await self.cursor.execute(sql, (ctx.guild.id, user.id, ctx.author.id))
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Guild blacklisted `{0}` from the bot.'.format(user))
		else:
			sql = 'DELETE FROM `blacklist` WHERE guild={0} AND user={1}'
			sql = sql.format(ctx.guild.id, user.id)
			await self.cursor.execute(sql)
			await ctx.send(':negative_squared_cross_mark: Guild unblacklisted `{0}` from the bot.'.format(user))

		self.query_blacklist.invalidate(self.bot.funcs, 3, ctx.guild.id, user.id)

	@blacklist.command(name='global')
	@commands.is_owner()
	async def blacklist_global(self, ctx, *, user:discord.User):
		"""Blacklist/Unblacklist user from guild"""
		if await self.bot.is_owner(user):
			return await ctx.send("what are you doing NotSoSuper?")
		sql = 'SELECT * FROM `global_blacklist` WHERE user={0}'.format(user.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		if not result:
			sql = 'INSERT INTO `global_blacklist` (`user`) VALUES (%s)'
			await self.cursor.execute(sql, (user.id,))
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Global blacklisted `{0}` from the bot.'.format(user))
		else:
			sql = 'DELETE FROM `global_blacklist` WHERE user={0}'.format(user.id)
			await self.cursor.execute(sql)
			await ctx.send(':negative_squared_cross_mark: Global unblacklisted `{0}` from the bot.'.format(user))

		self.query_blacklist.invalidate(self.bot.funcs, 1, user.id)

	@blacklist.command(name='channel')
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def blacklist_channel(self, ctx, chan:discord.TextChannel=None):
		"""Blacklists a channel from the bot."""
		if chan is None:
			chan = ctx.channel
		sql = 'SELECT * FROM `channel_blacklist` WHERE guild={0} AND channel={1}'
		sql = sql.format(ctx.guild.id, chan.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			sql = 'INSERT INTO `channel_blacklist` (`guild`, `channel`, `admin`) VALUES (%s, %s, %s)'
			await self.cursor.execute(sql, (ctx.guild.id, chan.id, ctx.author.id))
			await ctx.send("\N{WHITE HEAVY CHECK MARK} Blacklisted {0.mention} `<{0.id}>`".format(chan))
		else:
			sql = 'DELETE FROM `channel_blacklist` WHERE guild={0} AND channel={1}'
			sql = sql.format(ctx.guild.id, chan.id)
			await self.cursor.execute(sql)
			await ctx.send("\N{WHITE HEAVY CHECK MARK} Unblacklisted {0.mention} `<{0.id}>`".format(chan))

		self.query_blacklist.invalidate(self.bot.funcs, 4, chan.id)

	@blacklist.command(name='except', aliases=['exempt'])
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def blacklist_except(self, ctx, *roles:discord.Role):
		"""Blacklists everyone except specified roles."""
		if not roles:
			return await ctx.send('\N{NO ENTRY} `Please specify role(s) to exempt from blacklist.`')
		removed = []
		added = []
		for role in roles[:5]:
			sql = f'SELECT * FROM `except_blacklist` WHERE guild={ctx.guild.id} AND role={role.id}'
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			if not result:
				sql = 'INSERT INTO `except_blacklist` (`guild`, `role`, `admin`) VALUES (%s, %s, %s)'
				await self.cursor.execute(sql, (ctx.guild.id, role.id, ctx.author.id))
				added.append(role.name)
			else:
				sql = f'DELETE FROM `except_blacklist` WHERE guild={ctx.guild.id} AND role={role.id}'
				await self.cursor.execute(sql)
				removed.append(role.name)

		self.query_blacklist.invalidate(self.bot.funcs, 2, ctx.guild.id, single=False)

		msg = "\N{WHITE HEAVY CHECK MARK}"
		if added:
			msg += f"\n**Added**: `{', '.join(added)}`"
		if removed:
			msg += f"\n**Removed**: `{', '.join(removed)}`"
		await ctx.send(msg)

	@blacklist.command(name='list')
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@commands.guild_only()
	async def blacklist_list(self, ctx):
		sql = 'SELECT channel,admin,time FROM `channel_blacklist` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		entries = []
		found = False
		for s in result:
			channel = ctx.guild.get_channel(s['channel'])
			if channel is None:
				channel = '**Not found on guild** ID: `{0}`'.format(s['channel'])
			else:
				channel = channel.mention
			entries.append('\N{NO ENTRY} Channel: {0} | Admin: `{1}` | Time: `{2}`'.format(channel, await self.find_member(ctx.message, s['admin']),
																																									 	 self.format_time(s['time'])))
			if not found:
				found = True
		sql = f'SELECT role,admin,time FROM `except_blacklist` WHERE guild={ctx.guild.id}'
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		for s in result:
			entries.append('\N{WARNING SIGN} Except Role: `{0}` | Admin: `{1}` | Time: `{2}`'.format(discord.utils.get(ctx.guild.roles, id=s['role']),
																																														 	 await self.find_member(ctx.message, s['admin']),
																																														 	 self.format_time(s['time'])))
			if not found:
				found = True
		sql = f'SELECT user,admin,time FROM `blacklist` WHERE guild={ctx.guild.id}'
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		is_owner = await self.bot.is_owner(ctx.author)
		for s in result:
			entries.append('\N{NO ENTRY} User: `{0}` | Admin: `{1}` | Time: `{2}`'.format(await self.find_member(ctx.message, s['user']),
																																										await self.find_member(ctx.message, s['admin']),
																																										self.format_time(s['time'])))
			if not found:
				found = True
		if is_owner:
			sql = 'SELECT user,time FROM `global_blacklist`'
			q = await self.cursor.execute(sql)
			result = await q.fetchall()
			if result:
				for s in result:
					entries.append('\N{GLOBE WITH MERIDIANS} **Global Blacklisted** User: `{0}` | Time: `{1}`'.format(await self.find_member(ctx.message,s['user']),
																																																						self.format_time(s['time'])))
					if not found:
						found = True
		if found is False:
			return await ctx.send('\N{NO ENTRY} Guild does **not** have any channels or users blacklisted.')
		try:
			p = Pages(ctx, entries=entries, per_page=25, show_zero=False)
			p.embed.title = 'Blacklist'
			p.embed.color = self.bot.funcs.get_color()()
			p.embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url)
			await p.paginate()
		except CannotPaginate:
			await ctx.send('\n'.join(entries))

	def hierarchy_check(self, user, author):
		assert not (user.id == self.bot.user.id or \
						(author != user.guild.owner_id and user == user.guild.owner_id))
		assert user.guild.owner_id == author.id or \
						author.top_role > user.top_role

	async def muted_check(self, ctx, user):
		author = ctx.author
		if await self.bot.is_owner(author):
			return True
		elif not isinstance(user, discord.Member):
			return f"\N{WARNING SIGN} `{user}` is not on the server."
		try:
			if user.permissions_in(ctx.channel).administrator and user.guild.owner_id != author.id:
				assert False
			if user.id == 124912108470140928: # feldi shall be muted and off'd
				assert True
			else:
				self.hierarchy_check(user, author)
		except AssertionError:
			return f'\N{NO ENTRY} `{user}` is above your top role or the same.'

	@commands.group(invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True, check_channel_perms=False)
	async def off(self, ctx, *users:discord.Member):
		if not users:
			return await ctx.send('\N{NO ENTRY} Please input user(s) to turn off.')
		for user in users[:5]:
			if user == ctx.me:
				return await ctx.send("thanks for trying to turn me off, but u can't.\nasshole")

			check = await self.muted_check(ctx, user)
			if isinstance(check, str):
				return await ctx.send(check)

			sql = f"SELECT user FROM `muted` WHERE guild={ctx.guild.id} AND user={user.id}"
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			if result:
				return await ctx.send(f"`{user}` is already turned off!")

			self.is_off.invalidate(self.bot.funcs, ctx.guild.id, user.id)

			sql = "INSERT INTO `muted` (`guild`, `user`) VALUES (%s, %s)"
			await self.cursor.execute(sql, (ctx.guild.id, user.id))

			if isinstance(user, discord.Member):
				if user.voice and user.voice.channel.permissions_for(ctx.me).move_members:
					await user.edit(voice_channel=None)

		await ctx.send("ok, turned off `{0}`".format(', '.join(map(str, users))))

	@off.command(name='list', invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(1, 5)
	async def off_list(self, ctx):
		sql = 'SELECT * FROM `muted` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does **not** have any users turned off!')
		entries = []
		for s in result:
			try:
				user = await ctx.guild.fetch_member(s['user'])
			except discord.NotFound:
				user = await self.bot.fetch_user(s['user'])
			entries.append(f'"{user}" `(ID: {user.id})`')
		try:
			p = Pages(ctx, entries=entries, per_page=25, show_zero=False)
			p.embed.title = 'Users turned off'
			p.embed.color = self.bot.funcs.get_color()()
			p.embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url)
			await p.paginate()
		except CannotPaginate:
			msg = '\N{WHITE HEAVY CHECK MARK} Users turned off:\n'
			await ctx.send(msg + '\n'.join(f"**{i}.** {u}" for i, u in enumerate(entries)))

	async def do_on(self, guild, member):
		self.is_off.invalidate(self.bot.funcs, guild, member)

		sql = f"DELETE FROM `muted` WHERE guild={guild.id} AND user={member.id}"
		await self.cursor.execute(sql)

	@commands.group(invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True, check_channel_perms=False)
	async def on(self, ctx, *users:discord.User):
		if not users:
			return await ctx.send('\N{NO ENTRY} Please input user(s) to turn on.')
		for user in users:
			if user == ctx.me:
				return await ctx.send("thanks for trying to turn me on, but u can't.\nasshole")


			sql = f"SELECT user FROM `muted` WHERE guild={ctx.guild.id} AND user={user.id}"
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			if not result:
				return await ctx.send("`{0}` is already turned on!".format(user))

			self.is_off.invalidate(self.bot.funcs, ctx.guild.id, user.id)

			await self.do_on(ctx.guild, user)

		await ctx.send("ok, turned on `{0}`".format(', '.join(map(str, users))))

	@on.command(name='all', invoke_without_command=True)
	@commands.guild_only()
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def on_all(self, ctx):
		sql = 'SELECT COUNT(*) FROM `muted` WHERE guild={0}'.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		count = result['COUNT(*)']
		if count == 0:
			await ctx.send('\N{NO ENTRY} Guild does **not** have any users turned off!')
		else:
			self.is_off.invalidate_containing(str(ctx.guild.id))

			sql = 'DELETE FROM `muted` WHERE guild={0}'.format(ctx.guild.id)
			await self.cursor.execute(sql)
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Turned on `{0}` users.'.format(count))


	@commands.Cog.listener()
	async def on_message(self, message):
		await self.bot.wait_until_ready()
		if message.guild is None or message.author == self.bot.user:
			return
		if await self.is_off(message.guild.id, message.author.id):
			try:
				self.bot.pruned_messages.append(message.id)
				await message.delete()
			except discord.Forbidden:
				await self.do_on(message.guild, message.author)
			except:
				pass

	@commands.Cog.listener()
	async def on_voice_state_update(self, g, member, before, after):
		if not after.channel:
			return
		if not isinstance(member, int):
			member = member.id
		if after.channel.permissions_for(g.me).move_members and await self.is_off(g.id, member):
			http = g._state.http
			try:
				await http.edit_member(
					g.id, member,
					reason=None,
					channel_id=None
				)
			except discord.NotFound:
				pass # ok lol

	async def is_muted(self, guild, user):
		sql = 'SELECT user FROM `muted2` WHERE guild={0.id} AND user={1.id}'.format(guild, user)
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		return bool(result)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		if not await self.is_muted(member.guild, member):
			return
		await self.do_mute(member.guild, member, "Remute on rejoin")

	async def do_mute(self, guild, user, reason):
		for count, channel in enumerate(guild.channels):
			if not isinstance(channel, discord.TextChannel):
				continue
			perms = user.permissions_in(channel)
			if not perms.send_messages:
				continue
			perms = channel.permissions_for(guild.me)
			if not perms.manage_channels:
				continue
			try:
				await channel.set_permissions(user, send_messages=False, add_reactions=False, reason=reason)
			except:
				if count == 0:
					return False
				continue

	@commands.group(invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_channels=True)
	@checks.mod_or_perm(manage_messages=True, check_channel_perms=False)
	async def mute(self, ctx, *, user:discord.Member):
		"""Mute a User"""
		check = await self.muted_check(ctx, user)
		if isinstance(check, str):
			return await ctx.send(check)
		elif await self.is_muted(ctx.guild, user):
			return await ctx.send(f'`{user}` is already muted!')
		elif not isinstance(user, discord.Member):
			return await ctx.send(f'\N{WARNING SIGN} `{user}` is not on the server!')
		reason = f"Mute by {ctx.author}"
		if await self.do_mute(ctx.guild, user, reason) is False:
			await ctx.send("\N{NO ENTRY} Bot does not have permission.")
		else:
			await self.cursor.execute('INSERT INTO `muted2` (`guild`, `user`) VALUES (%s, %s)', (ctx.guild.id, user.id))
			await ctx.send("ok, muted `{0}`".format(user))

	@mute.command(name='list')
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def mute_list(self, ctx):
		q = await self.cursor.execute('SELECT * FROM `muted2` WHERE guild=%s', (ctx.guild.id,))
		result = await q.fetchall()
		if not result:
			return await ctx.send('\N{NO ENTRY} Guild does **not** have any users muted!')
		entries = []
		for s in result:
			uid = s['user']
			try:
				user = await ctx.guild.fetch_member(uid)
			except discord.NotFound:
				await self.cursor.execute(f'DELETE FROM `muted2` WHERE guild={ctx.guild.id} AND user={uid}')
				continue
			entries.append(f'"{user}" `(ID: {user.id})`')
		try:
			p = Pages(ctx, entries=entries, per_page=25, show_zero=False)
			p.embed.title = 'Muted Users'
			p.embed.color = self.bot.funcs.get_color()()
			p.embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url)
			await p.paginate()
		except CannotPaginate:
			msg = '\N{WHITE HEAVY CHECK MARK} Users muted:\n'
			await ctx.send(msg + '\n'.join(f"**{i}.** {u}" for i, u in enumerate(entries)))

	@commands.group(invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_channels=True)
	@checks.mod_or_perm(manage_messages=True, check_channel_perms=False)
	async def unmute(self, ctx, *users:discord.Member):
		"""Unmute a User"""
		if not users:
			return await ctx.send('idk who 2 unmute?????')
		ents = []
		not_muted = []
		reason = f"Unmute by {ctx.author}"
		for user in users[:5]:
			if not await self.is_muted(ctx.guild, user):
				not_muted.append(user)
				continue
			elif isinstance(user, discord.Member):
				for count, channel in enumerate(ctx.guild.channels):
					perms = user.permissions_in(channel)
					if not perms.read_messages:
						continue
					perms = channel.permissions_for(ctx.me)
					if not perms.manage_channels:
						continue
					try:
						await channel.set_permissions(user, overwrite=None, reason=reason)
					except:
						if count == 0:
							return await ctx.send("\N{NO ENTRY} Bot does not have permission")
						continue
			await self.cursor.execute('DELETE FROM `muted2` WHERE guild={0.id} AND user={1.id}'.format(ctx.guild, user))
			ents.append(user)

		msg = ""
		if ents:
			msg += "ok, unmuted `{0}`".format(', '.join(map(str, ents)))
		if not_muted:
			msg += f"\n`{', '.join(map(str, ents))}` were not muted."
		await ctx.send(msg)

	@commands.command()
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def leaveserver(self, ctx):
		"""bye"""
		await ctx.send("bye beautiful people :wave:")
		await ctx.guild.leave()

	@commands.group(invoke_without_command=True, aliases=['nickname'])
	@commands.guild_only()
	@checks.bot_has_perms(manage_nicknames=True)
	@checks.mod_or_perm(manage_nicknames=True)
	async def nick(self, ctx, *, nickname:str):
		"""Change a user(s) nickname"""
		mentions = ctx.message.mentions
		if not mentions:
			return await ctx.send('\N{NO ENTRY} `Please mention user(s) to change nickname of.`')
		changed = []
		for x in mentions:
			nickname = nickname.replace(f"<@{x.id}>", '').replace(f"<@!{x.id}>", '')
		if len(nickname) > 32:
			nickname = nickname[:32]
		for user in mentions[:8]:
			if user.top_role.position >= ctx.guild.me.top_role.position:
				await ctx.send(
					f"\N{WARNING SIGN} Cannot change `{user}`'s nickname, their role is above or equal to mine."
				)
			else:
				try:
					self.hierarchy_check(user, ctx.author)
				except AssertionError:
					await ctx.send(f'\N{NO ENTRY} `{user}` is above your top role or the same.')
				else:
					await user.edit(nick=nickname)
					changed.append(user)
		if changed:
			await ctx.send(
				"ok, changed the nickname of `{0}` to `{1}`".format(
					', '.join([str(x) for x in changed]), nickname
			))

	async def confirm_nick_mass(self, ctx, msg):
		x = await ctx.send(msg)
		def check(m):
			return m.channel == ctx.channel and m.author == ctx.author and m.content.lower() in ('y', 'yes')
		try:
			return await self.bot.wait_for('message', check=check, timeout=10)
		except asyncio.TimeoutError:
			await x.delete()
			await ctx.send('\N{NO ENTRY} `No confirmation, canceling.`', delete_after=5)
			return None

	async def change_nick(self, ctx, member, name):
		if '{' in name:
			ctx = copy(ctx)
			ctx.author = member
			name = await self.bot.get_cog('Tags').parse(ctx, name, "")
		if len(name) > 32:
			return False
		await member.edit(nick=name)

	@nick.group(name='mass', aliases=['massnick'], invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(1, 60, commands.BucketType.guild)
	@checks.bot_has_perms(manage_nicknames=True)
	@checks.admin_or_perm(manage_guild=True)
	async def nick_mass(self, ctx, *, name:str):
		"""Change everyones nickname"""
		g = ctx.guild
		if g.id in self.nick_massing:
			return await ctx.send('lol no, already nick massing asshole.')
		elif g.id in self.nick_unmassing:
			return await ctx.send('lol no, already nick unmassing asshole.')

		cmsg = "\N{WARNING SIGN} Are you **SURE** you want to change everyones " \
					 f"nickname to `{name}`: reply with `yes`."
		if not await self.confirm_nick_mass(ctx, cmsg):
			return

		await ctx.send("this might take a while, pls wait")
		try:
			# prevent runtime errors if guild members change
			coros = []
			mcount = 0
			async for member in g.fetch_members(limit=None):
				if member.nick == name or member.top_role.position >= g.me.top_role.position:
					continue
				coros.append(self.change_nick(ctx, member, name))
				mcount += 1

			fut = asyncio.gather(*coros, return_exceptions=True)
			self.nick_massing[g.id] = fut
			await fut

			result = fut.result()
			count = sum(1 for i in result if not isinstance(i, Exception))
			tl = count = sum(1 for i in result if i is False)
			forbidden = sum(1 for i in result if isinstance(i, discord.Forbidden))
			httperror = sum(1 for i in result if isinstance(i, discord.HTTPException)) - forbidden
			failed = mcount - count
			await ctx.send(
				f"ok, changed the nickname of `{count}` users, " \
				f"failed/already changed `{failed}` " \
				f"(`{forbidden}` forbidden, {tl} too long, `{httperror}` rate limit/other)."
			)
		except asyncio.CancelledError:
			pass
		finally:
			del self.nick_massing[g.id]

	@nick_mass.command(name='revert', aliases=['unick', 'unmass', 'reset'])
	@commands.guild_only()
	@commands.cooldown(1, 60, commands.BucketType.guild)
	@checks.bot_has_perms(manage_nicknames=True)
	@checks.admin_or_perm(manage_guild=True)
	async def nick_mass_revert(self, ctx):
		"""Default every users nickname in the guild"""
		g = ctx.guild
		if g.id in self.nick_massing:
			return await ctx.send('lol no, already nick massing asshole.')
		elif g.id in self.nick_unmassing:
			return await ctx.send('lol no, already nick unmassing asshole.')

		cmsg = f'\N{WARNING SIGN} Are you **SURE** you want to remove everyones nickname?'
		if not await self.confirm_nick_mass(ctx, cmsg):
			return

		await ctx.send("this might take a while, pls wait")
		try:
			coros = []
			mcount = 0
			async for member in g.fetch_members(limit=None):
				if not member.nick or member.top_role.position >= g.me.top_role.position:
					continue
				coros.append(member.edit(nick=None))
				mcount += 1

			fut = asyncio.gather(*coros, return_exceptions=True)
			self.nick_unmassing[g.id] = fut
			await fut

			result = fut.result()
			count = sum(1 for i in result if not isinstance(i, Exception))
			forbidden = sum(1 for i in result if isinstance(i, discord.Forbidden))
			httperror = sum(1 for i in result if isinstance(i, discord.HTTPException)) - forbidden
			failed = mcount - count
			await ctx.send(
				f"ok, reset the nickname of `{count}` users, " \
				f"failed/already changed `{failed}` " \
				f"(`{forbidden}` forbidden, `{httperror}` rate limit/other)."
			)
		except asyncio.CancelledError:
			pass
		finally:
			del self.nick_unmassing[g.id]

	@nick_mass.command(name='cancel', aliases=['stop'])
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_nicknames=True)
	@checks.admin_or_perm(manage_guild=True)
	async def nick_mass_cancel(self, ctx):
		"""Cancel a nick mass or unmass"""
		lookup = (self.nick_massing, self.nick_unmassing)
		gid = ctx.guild.id
		for d in lookup:
			if gid in d:
				d[gid].cancel()
				return await ctx.send("\N{WHITE HEAVY CHECK MARK} Cancelled `nick mass/unmass`.")

		return await ctx.send("\N{WARNING SIGN} No `nick mass` event is going on.")

	@commands.command()
	@commands.guild_only()
	@checks.bot_has_perms(manage_guild=True)
	@checks.mod_or_perm(manage_guild=True)
	async def invites(self, ctx):
		"""List all Guild Invites"""
		invites = await ctx.guild.invites()
		if not invites:
			await ctx.send("\N{WARNING SIGN} There currently no invites active.")
		else:
			invites = ", ".join(map(str, invites))
			await ctx.send(f"Invites: {invites}", hastebin=True)

	@commands.group(invoke_without_command=True)
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def pin(self, ctx, max_messages:int=2000, *, txt:str):
		"""Attempt to find a Message by ID or Content and Pin it"""
		if max_messages > 5000:
			return await ctx.send("2 many messages (> 5000)")
		async for message in ctx.channel.history(before=ctx.message, limit=max_messages):
			if f'{message.id}' == txt:
				try:
					await message.pin()
				except:
					return await ctx.send("\N{WARNING SIGN} Maximum Pins Reached (50).")
				else:
					return await ctx.send("\N{SQUARED OK} Pinned Message with Given ID")
			elif txt in message.content:
				try:
					await message.pin()
				except:
					return await ctx.send("\N{WARNING SIGN} Maximum Pins Reached (50).")
				else:
					return await ctx.send("\N{SQUARED OK} Pinned Message with given text in it!")
			else:
				continue
		await ctx.send("\N{HEAVY EXCLAMATION MARK SYMBOL} No message found with ID or Content given!")

	@pin.command(name='date')
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def pin_date(self, ctx, date:str, channel:discord.TextChannel=None):
		"""Pin a message after the specified date\nUse the \"pin first\" command to pin the first message!"""
		_date = None
		fmts = ('%Y/%m/%d', '%Y-%m-%d', '%m-%d-%Y', '%m/%d/%Y')
		for s in fmts:
			try:
				_date = datetime.datetime.strptime(date, s)
			except ValueError:
				continue
		if _date is None:
			return await ctx.send(
				"\N{WARNING SIGN} Cannot convert to date. Formats: " \
				"`YYYY/MM/DD, YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY`"
			)
		if channel is None:
			channel = ctx.channel
		async for message in channel.history(after=_date, limit=1):
			try:
				await message.pin()
			except:
				return await ctx.send("\N{WARNING SIGN} Maximum Pins Reached (50).")
			else:
				return await ctx.send("\N{SQUARED OK} Pinned Message with date \"{0}\"!".format(str(_date)))
		await ctx.send("\N{HEAVY EXCLAMATION MARK SYMBOL} No message found with date given!")

	@pin.command(name='before')
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def pin_before(self, ctx, date:str, max_messages:int=2000, *, txt:str):
		"""Pin a message before a certain date"""
		if max_messages > 2000:
			return await ctx.send("2 many messages (> 2000")
		_date = None
		fmts = ('%Y/%m/%d', '%Y-%m-%d', '%m-%d-%Y', '%m/%d/%Y')
		for s in fmts:
			try:
				_date = datetime.datetime.strptime(date, s)
			except ValueError:
				continue
		if _date is None:
			return await ctx.send(
				"\N{WARNING SIGN} Cannot convert to date. Formats: " \
				"`YYYY/MM/DD, YYYY-MM-DD, MM-DD-YYYY, MM/DD/YYYY`"
			)
		for c in ctx.message.channel_mentions:
			channel = c
			txt = txt.replace(c.mention, '')
		else:
			channel = ctx.channel
		async for message in channel.history(before=_date, limit=max_messages):
			if txt in message.content:
				try:
					await message.pin()
				except:
					return await ctx.send("\N{WARNING SIGN} Maximum Pins Reached (50).")
				else:
					return await ctx.send("\N{SQUARED OK} Pinned Message before date \"{0}\" with given text!".format(str(_date)))
		await ctx.send("\N{HEAVY EXCLAMATION MARK SYMBOL} No message found with given text before date given!")

	@pin.command(name='first', aliases=['firstmessage'])
	@checks.bot_has_perms(manage_messages=True)
	@checks.mod_or_perm(manage_messages=True)
	async def pin_first(self, ctx, channel:discord.TextChannel=None):
		"""Pin the first message in current/specified channel!"""
		if channel is None:
			channel = ctx.channel
		date = str(ctx.channel.created_at).split()[0]
		_date = datetime.datetime.strptime(date, '%Y-%m-%d')
		async for message in channel.history(after=_date, limit=1):
			try:
				await message.pin()
			except:
				return await ctx.send("\N{WARNING SIGN} Maximum Pins Reached (50).")
			else:
				return await ctx.send("\N{SQUARED OK} Pinned First Message with date \"{0}\"!\n**Message Info**\nAuthor: `{1}`\nTime: `{2}`\nContent: \"{3}\"".format(str(_date), message.author.name,
																																																																															self.format_time(message.created_at),
																																																																															message.content[:1500]), replace_mentions=True)
		await ctx.send("\N{HEAVY EXCLAMATION MARK SYMBOL} No first message found!")

	@commands.command()
	@checks.bot_has_perms(ban_members=True)
	@checks.admin_or_perm(ban_members=True)
	async def hackban(self, ctx, *users:int):
		if not users:
			return await ctx.send('idk who 2 ban?????')
		banned = []
		for user in users[:5]:
			try:
				u = await ctx.guild.fetch_member(user)
				await ctx.send('`{0}` is already on the guild and could not be banned.'.format(u))
				continue
			except discord.NotFound:
				pass
			try:
				await ctx.guild.ban(discord.Object(id=user), delete_message_days=0, reason='hackban')
				banned.append(str(user))
			except:
				await ctx.send('`{0}` could not be hack banned/found.'.format(user))
				continue
		if banned:
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Hackbanned `{0}`!'.format(", ".join(banned)))

	async def role_check(self, role, user, guild):
		return role.position >= user.top_role.position and user.id != guild.owner_id

	@commands.command()
	@commands.guild_only()
	@checks.bot_has_perms(manage_roles=True)
	@checks.admin_or_perm(manage_roles=True)
	async def addrole(self, ctx, role:discord.Role, *users:discord.User):
		"""Add a role to x users"""
		if not users:
			return await ctx.send("\N{NO ENTRY} You need to specify a user to give the role too.")
		if await self.role_check(role, ctx.author, ctx.guild):
			return await ctx.send('\N{NO ENTRY} `That role is above your top role or the same.`')
		for user in users:
			await user.add_roles(role)
		await ctx.send("ok, gave {0} `{1}` the role **{2}**".format('user' if len(users) == 1 else 'users', ', '.join(map(str, users)), role.name))

	@commands.command()
	@commands.guild_only()
	@checks.bot_has_perms(manage_roles=True)
	@checks.admin_or_perm(manage_roles=True)
	async def removerole(self, ctx, role:discord.Role, *users:discord.User):
		"""Remove a role from x users"""
		if not users:
			return await ctx.send("\N{NO ENTRY} You need to specify a user to remove the role from.")
		if await self.role_check(role, ctx.author, ctx.guild):
			return await ctx.send('\N{NO ENTRY} `That role is above your top role or the same.`')
		for user in users:
			await user.remove_roles(role)
		await ctx.send("ok, removed the role **{0}** from {2} `{1}`".format(role.name, ', '.join(map(str, users)), 'user' if len(users) == 1 else 'users'))

def setup(bot):
	bot.add_cog(Moderation(bot))
