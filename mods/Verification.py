import discord
import asyncio
import random
import aiosteam
from discord.ext import commands
from utils import checks
from mods.cog import Cog

class Verification(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.escape = bot.escape
		self._task = bot.loop.create_task(self.verification_task())

	def cog_unload(self):
		self._task.cancel()

	async def remove_verification(self, guild, idk=None):
		role = discord.utils.get(guild.roles, name='Awaiting Approval')
		if role:
			try:
				await role.delete()
			except:
				pass
		sql = 'DELETE FROM `verification` WHERE guild={0}'.format(guild.id)
		await self.cursor.execute(sql)
		sql = 'DELETE FROM `verification_queue` WHERE guild={0}'.format(guild.id)
		await self.cursor.execute(sql)
		if idk is None:
			try:
				await guild.owner.send("\N{WARNING SIGN} One of your guild administrators (or you) have enabled approval/verification on user join.\n\nAdministrator permission was taken away from me making the feature unusable, I need Administrator permission to make/add a role to mute on join.\n\n`The system has been automatically disabled, re-enable anytime if you please.`")
			except:
				pass

	async def awaiting_role(self, guild):
		try:
			if any(x.name == 'Awaiting Approval' for x in guild.roles):
				return True
			permissions = discord.Permissions()
			permissions.read_messages = True
			return await guild.create_role(name='Awaiting Approval', color=discord.Colour(int("FF0000", 16)), permissions=permissions)
		except:
			return False

	@commands.group(aliases=['onjoinverify', 'approval'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def verification(self, ctx, channel:discord.TextChannel=None, *, mentions:str=None):
		perms = ctx.guild.me.permissions_in(ctx.channel)
		if perms.manage_roles is False or perms.manage_channels is False:
			if perms.administrator is False:
				await ctx.send("\N{WARNING SIGN} `I need Administrator permission to make/add a role to mute on join`")
				return
		if channel is None:
			channel = ctx.channel
		sql = 'SELECT * FROM `verification` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if len(result) == 0:
			if mentions is None:
				sql = "INSERT INTO `verification` (`guild`, `channel`) VALUES (%s, %s)"
				await self.cursor.execute(sql, (ctx.guild.id, channel.id))
				await ctx.send("\N{WHITE HEAVY CHECK MARK} Enabled user approval/verification on join, all requests will go to {0} (`verification #<discord_channel>` to change)!".format(channel.mention))
			else:
				if len(ctx.message.mentions) == 0:
					await ctx.send("invalid mention")
					return
				sql = "INSERT INTO `verification` (`guild`, `channel`, `mentions`) VALUES (%s, %s, %s)"
				mention_ids = []
				mention_names = []
				for mention in ctx.message.mentions:
					mention_ids.append(mention.id)
					mention_names.append(mention.name)
				await self.cursor.execute(sql, (ctx.guild.id, channel.id, ' '.join(map(str, mention_ids))))
				await ctx.send("\N{WHITE HEAVY CHECK MARK} Enabled user approval/verification on join, all requests will go to {0} (`verification <#discord_channel>` to change) and mention `{0}`!".format(channel.mention, ', '.join(mention_names)))
			result = await self.awaiting_role(ctx.guild)
			if not result:
				await ctx.send("\N{WARNING SIGN} For some reason I couldn't create the \"Awaiting Approval\" role and users won't be muted, please create it (same name) and disable all the permissions you don't want unapproved-users to have.\nMake sure I have the administrator permission!")
		elif channel is None:
			sql = 'UPDATE `verification` SET channel={0} WHERE guild={1}'
			sql = sql.format(channel.id, ctx.guild.id)
			await self.cursor.execute(sql)
			await ctx.send("\N{WHITE HEAVY CHECK MARK} Set approval/verification channel to {0}".format(channel.mention))
		else:
			await ctx.send('\N{WARNING SIGN} You are about to disable member verification/approval on join, type `yes` to proceed.')
			try:
				response = await self.bot.wait_for('message', timeout=15, check=lambda m: m.content == 'yes' and m.author == ctx.author and m.channel == ctx.channel)
			except asyncio.TimeoutError:
				await ctx.send('**Aborting**')
			else:
				await self.remove_verification(ctx.guild, True)
				try:
					role = discord.utils.get(ctx.guild.roles, name='Awaiting Approval')
					if role != None:
						await role.delete()
				except discord.Forbidden:
					await ctx.send("could not remove role, you took my perms away :(")
				role2 = discord.utils.get(ctx.guild.roles, name='Approved')
				if role2 != None:
					try:
						await role2.delete()
					except:
						pass
				await ctx.send(":negative_squared_cross_mark: **Disabled** user approval on join")

	@verification.command(name='mention', aliases=['mentions'], invoke_without_command=True)
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def verification_mention(self, ctx, *mentions:str):
		perms = ctx.guild.me.permissions_in(ctx.channel)
		if perms.manage_roles is False or perms.manage_channels is False:
			if perms.administrator is False:
				await ctx.send("\N{WARNING SIGN} `I need Administrator permission to make/add a role to mute on join`")
				return
		if len(ctx.message.mentions) == 0 and '@everyone' not in mentions and '@here' not in mentions:
			await ctx.send('\N{NO ENTRY} `Invalid mention(s).`')
			return
		sql = 'SELECT * FROM `verification` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send("\N{NO ENTRY} This guild does not have approval/verification turned on (`verification <#discord_channel>` to do so)!!!")
		if not mentions:
			sql = 'UPDATE `verification` SET mentions=NULL WHERE guild={0}'
			sql = sql.format(ctx.guild.id)
			await self.cursor.execute(sql)
			await ctx.send(":negative_squared_cross_mark: Disabled/Removed mentions on user join for approval")
		else:
			mention_ids = []
			mention_names = []
			everyone = False
			for mention in mentions:
				if mention == '@everyone':
					mention_ids.append('@everyone')
				elif mention == '@here':
					mention_ids.append('@here')
			for mention in ctx.message.mentions:
				mention_ids.append(mention.id)
				mention_names.append(mention.name)
			sql = 'SELECT mentions FROM `verification` WHERE guild={0}'
			sql = sql.format(ctx.guild.id)
			q = await self.cursor.execute(sql)
			mention_results = await q.fetchall()
			update = False
			if mention_results[0]['mentions'] != None:
				update = True
				things = mention_results[0]['mentions'].split()
				for x in things:
					mention_ids.append(x)
			sql = "UPDATE `verification` SET mentions={0} WHERE guild={1}"
			sql = sql.format(self.escape(' '.join(mention_ids)), ctx.guild.id)
			await self.cursor.execute(sql)
			if update:
				await ctx.send("\N{WHITE HEAVY CHECK MARK} Updated mentions to include `{0}` on user join for approval".format(', '.join(mention_names)))
			else:
				await ctx.send("\N{WHITE HEAVY CHECK MARK} Set `{0}` to be mentioned on user join for approval".format(', '.join(mention_names)))

	@commands.group(invoke_without_command=True)
	@commands.guild_only()
	@checks.mod_or_perm(manage_guild=True)
	async def verify(self, ctx, *users:str):
		perms = ctx.guild.me.permissions_in(ctx.channel)
		if perms.manage_roles is False or perms.manage_channels is False:
			if perms.administrator is False:
				await ctx.send("\N{WARNING SIGN} `I need Administrator permission to make/add a role to mute on join`")
				return
		if not users:
			return await ctx.send("pls input users to verify thx")
		sql = 'SELECT * FROM `verification` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send("\N{NO ENTRY} This guild does not have approval/verification turned **on** (`verification <#discord_channel>` to do so)!!!")
		role = discord.utils.get(ctx.guild.roles, name="Awaiting Approval")
		count = 0 
		count2 = 0
		discord_user = None
		for user in users[:5]:
			if user.isdigit():
				user = int(user)
				sql = 'SELECT * FROM `verification_queue` WHERE guild={0} AND id={1}'
				sql = sql.format(ctx.guild.id, user)
				q = await self.cursor.execute(sql)
				result = await q.fetchall()
				if not result:
					await ctx.send("\N{WARNING SIGN} `{0}` is not in the verification queue.".format(user))
					if len(users) > 1:
						continue
					return
				sql = 'DELETE FROM `verification_queue` WHERE guild={0} AND id={1}'
				sql = sql.format(ctx.guild.id, user)
				await self.cursor.execute(sql)
				discord_user = ctx.guild.get_member(result[count]['user'])
				count += 1
			else:
				if not ctx.message.mentions:
					return await ctx.send("If you're not gonna use approval id, atleast mention correctly!")
				for x in ctx.message.mentions:
					if count == len(ctx.message.mentions):
						break
					sql = 'SELECT * FROM `verification_queue` WHERE guild={0} AND user={1}'
					sql = sql.format(ctx.guild.id, x.id)
					q = await self.cursor.execute(sql)
					result = await q.fetchall()
					if not result:
						await ctx.send("\N{WARNING SIGN} `{0}` is not in the verification queue.".format(user))
						if len(users) > 1:
							continue
						return
					sql = 'DELETE FROM `verification_queue` WHERE guild={0} AND user={1}'
					sql = sql.format(ctx.guild.id, x.id)
					await self.cursor.execute(sql)
					discord_user = ctx.guild.get_member(result[count2]['user'])
					count2 += 1
			if discord_user is None:
				continue
			try:
				await discord_user.remove_roles(role)
			except Exception as e:
				await ctx.send(self.bot.funcs.format_code(e))
				await ctx.send("\N{WARNING SIGN} {0} was removed from the queue however his role could not be removed because I do not have Administrator permissions.\nPlease remove the role manually and give me **Administrator**.".format(user))
				return
			role = discord.utils.get(ctx.guild.roles, name='Approved')
			if role != None:
				try:
					await discord_user.add_roles(role)
				except:
					pass
			await ctx.send("\N{WHITE HEAVY CHECK MARK} Removed `{0}` from queue!".format(user))
			queue_removed_msg = 'You have been approved/verified for `{0}` and can now message!'.format(ctx.guild.name)
			await discord_user.send(queue_removed_msg)

	@verify.command(name='list', invoke_without_command=True)
	@commands.guild_only()
	async def verify_list(self, ctx):
		perms = ctx.guild.me.permissions_in(ctx.channel)
		if perms.manage_roles is False or perms.manage_channels is False:
			if perms.administrator is False:
				await ctx.send("\N{WARNING SIGN} `I need Administrator permission to make/add a role to mute on join`")
				return
		sql = 'SELECT * FROM `verification` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send("\N{NO ENTRY} This guild does not have approval/verification turned on (`verification <#discord_channel>` to do so)!!!")
		sql = 'SELECT * FROM `verification_queue` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send("\N{NO ENTRY} `There are no users in the verification/approval queue`")
		users = []
		for s in result:
			user = discord.Guild.get_member(ctx.guild, user_id=s['user'])
			if user is None:
				continue
			users.append('{0}#{1} ({2})'.format(user.name, user.discriminator, str(s['id'])))
		await ctx.send("**{0} Users in Queue**\n`{1}`".format(len(users), ', '.join(users)))

	# steam_regex = r"^(http|https|)(\:\/\/|)steamcommunity\.com\/id\/(.*)$"
	@verify.command(name='check', aliases=['steam', 'link'])
	async def verify_check(self, ctx, *, stem:str):
		try:
			if ctx.guild:
				return await ctx.send('\N{NO ENTRY} `Private Message only.`')
			sql = 'SELECT * FROM `verification_queue` WHERE user={0}'
			sql = sql.format(ctx.author.id)
			q = await self.cursor.execute(sql)
			result = await q.fetchall()
			if not result:
				return await ctx.send('\N{NO ENTRY} You are not in the verification queue for any guild.')
			guild_id = result[0]['guild']
			sql = 'SELECT * FROM `verification` WHERE guild={0}'
			sql = sql.format(guild_id)
			q = await self.cursor.execute(sql)
			result = await q.fetchall()
			if not result:
				return await ctx.send("\N{NO ENTRY} Guild you are in queue for disabled verification.")
			sql = 'SELECT * FROM `verification_steam` WHERE guild={0} AND user={1}'
			sql = sql.format(guild_id, ctx.author.id)
			q = await self.cursor.execute(sql)
			result = await q.fetchall()
			if result:
				return await ctx.send("\N{NO ENTRY} You've already verified your steam account!")
			sql = 'SELECT id,guild FROM `verification_queue` WHERE guild={0} AND user={1}'
			sql = sql.format(guild_id, ctx.author.id)
			q = await self.cursor.execute(sql)
			result = await q.fetchall()
			if not result:
				return await ctx.send("\N{WARNING SIGN} `{0}` is not in the verification queue.".format(ctx.author))
			verification_id = str(result[0]['id'])
			steam = await aiosteam.get_user(stem)
			if steam is None:
				return await ctx.send("`\N{NO ENTRY} `Bad Steam ID/64/URL`")
			if verification_id in steam.name:
				sql = 'INSERT INTO `verification_steam` (`user`, `guild`, `steam`, `id`) VALUES (%s, %s, %s, %s)'
				await self.cursor.execute(sql, (ctx.author.id, guild_id, steamId.profileUrl, verification_id))
				await ctx.send('\N{WHITE HEAVY CHECK MARK} `{0}` steam profile submitted and passed steam name check, awaiting moderator approval.'.format(ctx.author))
			else:
				await ctx.send('\N{WARNING SIGN} **{0}** is not in the steam accounts name.'.format(verification_id))
		except Exception as e:
			await ctx.send(self.bot.funcs.format_code(e))

	async def verification_task(self):
		while not self.bot.is_closed():
			sql = 'SELECT * FROM `verification_steam`'
			q = await self.cursor.execute(sql)
			result = await q.fetchall()
			if not result:
				await asyncio.sleep(60)
				continue
			for s in result:
				guild = self.bot.get_guild(s['guild'])
				if guild:
					user = guild.get_member(s['user'])
					if user is None:
						continue
					sql = 'SELECT channel FROM `verification` WHERE guild={0}'.format(guild.id)
					q = await self.cursor.execute(sql)
					channel = guild.get_channel((await q.fetchone())['channel'])
					msg = '**Steam Account Check**\n`{0} (Verification ID: {1})` has submitted their steam profile and passed the name check.\n`Steam Profile:` {2}'.format(user, s['id'], s['steam'])
					await channel.send(msg)
					sql = 'DELETE FROM `verification_steam` WHERE guild={0} AND user={1}'.format(guild.id, user.id)
					await self.cursor.execute(sql)
			await asyncio.sleep(60)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		try:
			if member.bot:
				return
			guild = member.guild
			sql = 'SELECT channel,mentions FROM `verification` WHERE guild={0}'.format(guild.id)
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			if not result:
				return
			channel = guild.get_channel(result['channel'])
			assert channel
			perms = guild.me.permissions_in(channel)
			if not perms.manage_roles or not perms.manage_channels:
				if not perms.administrator:
					return await self.remove_verification(guild)
			sql = "INSERT INTO `verification_queue` (`user`, `guild`, `id`) VALUES (%s, %s, %s)"
			rand = random.randint(0, 99999)
			await self.cursor.execute(sql, (member.id, guild.id, rand))
			role = discord.utils.get(guild.roles, name='Awaiting Approval')
			if not role:
				role = await self.awaiting_role(guild)
				assert role
			await member.add_roles(role)
			for s in guild.channels:
				perms = member.permissions_in(s)
				if perms.read_messages is False:
					continue
				overwrite = discord.PermissionOverwrite()
				await s.set_permissions(role, send_messages=False, read_messages=False, reason='Verification Setup')
			msg = ''
			if result['mentions']:
				for x in str(result['mentions']).split(' '):
					if 'everyone' in x or 'here' in x:
						msg += '{0} '.format(x)
					else:
						msg += '<@{0}> '.format(x)
				msg += '\n'
			msg += '\N{WARNING SIGN} `{0}` has joined the guild and is awaiting approval\n\nRun `verify {1} or mention` to approve, kick user to remove from the queue.'.format(member, rand)
			await channel.send(msg, replace_everyone=False, replace_mentions=False)
			join_msg = "You've been placed in the approval queue for `{0}`, please be patient and wait until a staff member approves your join!\n\nIf you'd like to expedite approval (and have a steam account), place **{1}** in your steam name and then run `.verify check <stean_url/id/vanity>`.".format(guild.name, rand)
			try:
				await member.send(join_msg)
			except:
				pass
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_verification(guild)

	@commands.Cog.listener()
	async def on_member_remove(self, member):
		try:
			if member.bot:
				return
			guild = member.guild
			sql = 'SELECT * FROM `verification` WHERE guild={0}'.format(guild.id)
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			if not result:
				return
			sql = 'SELECT * FROM `verification_queue` WHERE guild={0} AND user={1}'.format(guild.id, member.id)
			q = await self.cursor.execute(sql)
			if not await q.fetchone():
				return
			sql = 'DELETE FROM `verification_queue` WHERE guild={0} AND user={1}'.format(guild.id, member.id)
			await self.cursor.execute(sql)
			channel = self.bot.get_channel(result['channel'])
			assert channel
			await channel.send('\N{HEAVY EXCLAMATION MARK SYMBOL} `{0}` has been removed from the approval/verification queue for leaving the guild or being kicked.'.format(member))
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_verification(guild)

	@commands.Cog.listener()
	async def on_member_ban(self, guild, member):
		try:
			if member.bot:
				return
			sql = 'SELECT * FROM `verification` WHERE guild={0}'.format(guild.id)
			q = await self.cursor.execute(sql)
			result = await q.fetchone()
			if not result:
				return
			sql = 'SELECT * FROM `verification_queue` WHERE guild={0} AND user={1}'.format(guild.id, member.id)
			q = await self.cursor.execute(sql)
			if not await q.fetchone():
				return
			sql = 'DELETE FROM `verification_queue` WHERE guild={0} AND user={1}'.format(guild.id, member.id)
			await self.cursor.execute(sql)
			channel = self.bot.get_channel(result['channel'])
			assert channel
			await channel.send('\N{HEAVY EXCLAMATION MARK SYMBOL} `{0}` has been removed from the approval/verification queue for being banned from the guild.'.format(member))
		except (AssertionError, discord.Forbidden, discord.NotFound):
			await self.remove_verification(guild)

def setup(bot):
	bot.add_cog(Verification(bot))