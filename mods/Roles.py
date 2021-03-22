import discord
from discord.ext import commands

from mods.cog import Cog
from utils import checks


COLOR_ROLES = (
	'red',
	'green',
	'blue',
	'purple',
	'orange',
	'black',
	'white',
	'cyan',
	'lime',
	'pink',
	'yellow',
	'lightred',
	'lavender',
	'salmon',
	'darkblue',
	'darkpurple',
	'gold'
)

class Roles(Cog):

	@staticmethod
	def is_color(color, colors):
		return any(x for x in colors if x.name.lower() == color)

	async def get_colors(self, guild):
		q = await self.cursor.execute('SELECT role FROM `colors` WHERE guild=%s', (guild.id,))
		ids = [x['role'] for x in await q.fetchall()]
		cc = list(filter(lambda x: int(x.id) in ids, guild.roles))
		if len(ids) != len(cc):
			for i in ids:
				if i not in cc:
					await self.cursor.execute('DELETE FROM `colors` WHERE guild=%s AND role=%s', (guild.id, i))
					ids.remove(i)
		roles = filter(lambda x: int(x.id) in ids or x.name in COLOR_ROLES, guild.roles)
		return list(roles)

	@staticmethod
	def get_color(guild, name):
		return discord.utils.get(guild.roles, name=name)

	@staticmethod
	def has_color(guild, user, colors):
		return list(filter(lambda x: x in user.roles and x in colors, guild.roles))

	@commands.group(aliases=['colour'], invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.user)
	@checks.bot_has_perms(manage_roles=True)
	async def color(self, ctx, *, color:str=None):
		"""Set your color!"""
		if color is None:
			return await ctx.send("\N{WARNING SIGN} `You must input a color, run the colors command to see what you can choose!`")
		author = ctx.author
		if isinstance(author, discord.User):
			return await ctx.send("\N{NO ENTRY} Cannot get your roles!\nTry setting your presence to online.")
		color = color.lower()
		guild = ctx.guild
		colors = await self.get_colors(guild)
		if not self.is_color(color, colors):
			ctx.command.reset_cooldown(ctx)
			return await ctx.send('\N{NO ENTRY} `Invalid color, run the colors command to see what you can choose!`')
		uc = self.has_color(guild, author, colors)
		# role = self.get_color(guild, color)
		role = next(x for x in colors if x.name.lower() == color)
		if role in uc:
			return await ctx.send('\N{NO ENTRY} You already have that color, run **uncolor** first!')
		new_roles = [x for x in author.roles if x not in uc]
		new_roles.append(role)
		try:
			await author.edit(roles=new_roles, reason='color')
		except discord.Forbidden:
			await ctx.send('\N{WARNING SIGN} Either the color roles are __higher in the roles list than the bots__\nor the bots role does not have `manage_roles` permission.')
		else:
			if uc:
				await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Changed color from `{uc[0]}` to `{color}`.")
			else:
				await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Added color `{role}`.')


	@color.command(name='add')
	@commands.guild_only()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_roles=True)
	@checks.admin_or_perm(manage_roles=True)
	async def color_add(self, ctx, color:discord.Color, *, name:str):
		"""Add a color role with the inputted name and Hex Color"""
		if len(name) > 32:
			return await ctx.send('\N{NO ENTRY} `Role names cannot be longer than 32 characters.`')
		name = name.lower()
		guild = ctx.guild
		role = discord.utils.get(guild.roles, name=name)
		if role:
			return await ctx.send('\N{NO ENTRY} `Role name already exists.`')
		q = await self.cursor.execute('SELECT COUNT(*) FROM `colors` WHERE guild=%s', (guild.id,))
		count = (await q.fetchone())['COUNT(*)']
		if count > 30:
			return await ctx.send('\N{NO ENTRY} `Maximum color roles reached (30)!`')
		q = await self.cursor.execute('SELECT role FROM `colors` WHERE guild=%s and name=%s', (guild.id, name))
		if await q.fetchone():
			return await ctx.send('\N{NO ENTRY} `Color already exists.`')
		role = await self.create_role(guild, name=name, color=color)
		q = await self.cursor.execute('INSERT INTO `colors` (`guild`, `name`, `role`) VALUES (%s, %s, %s)', (guild.id, name, role.id))
		e = discord.Embed()
		e.description = f'Added color role `{name} ({color})`'
		e.color = color
		await ctx.send(embed=e)

	@color.command(name='remove', aliases=['delete'])
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.bot_has_perms(manage_roles=True)
	@checks.admin_or_perm(manage_roles=True)
	async def color_remove(self, ctx, *, name:str):
		guild = ctx.guild
		name = name.lower()
		role = discord.utils.get(guild.roles, name=name)
		if not role:
			return await ctx.send('\N{NO ENTRY} `Role does not exists.`')
		colors = await self.get_colors(guild)
		if role not in colors:
			return await ctx.send("\N{NO ENTRY} `That's not a color role!`")
		q = await self.cursor.execute('SELECT role FROM `colors` WHERE guild=%s AND name=%s', (guild.id, name))
		result = await q.fetchone()
		if result:
			await self.cursor.execute('DELETE FROM `colors` WHERE guild=%s AND role=%s', (guild.id, result['role']))
		await role.delete(reason='remove color')
		await ctx.send(f"\N{WHITE HEAVY CHECK MARK} Removed color `{role}`.")

	@commands.command(aliases=['uncolour'])
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.user)
	@checks.bot_has_perms(manage_roles=True)
	async def uncolor(self, ctx):
		"""Removes color if set."""
		colors = await self.get_colors(ctx.guild)
		colors = self.has_color(ctx.guild, ctx.author, colors)
		if colors:
			await ctx.author.remove_roles(*colors, reason='uncolor')
			await ctx.send(f"\N{NEGATIVE SQUARED CROSS MARK} Removed color `{', '.join(str(x) for x in colors)}`.")
		else:
			await ctx.send('\N{WARNING SIGN} `You have no color to remove!`')

	@commands.command(aliases=['colours'])
	@commands.guild_only()
	@commands.cooldown(1, 10, commands.BucketType.guild)
	@checks.bot_has_perms(manage_roles=True)
	async def colors(self, ctx):
		"""Returns color roles available to use in '.color' command."""
		colors = await self.get_colors(ctx.guild)
		if colors:
			await ctx.send("Colors Available:\n```{0}```\nUse .color <color_name> to set your color!".format(", ".join(str(x) for x in colors)))
		else:
			await ctx.send('\N{WARNING SIGN} `Guild does not have any color roles!`')

	async def create_role(self, guild, **kwargs):
		name = kwargs.get('name')
		if not discord.utils.get(guild.roles, name=name):
			role = await guild.create_role(**kwargs, reason='Color Role')
			colors = await self.get_colors(guild)
			if colors:
				colors = sorted(colors, key=lambda x: x.position)
				if len(colors) > 1:
					await role.edit(position=colors[1].position - 1, reason='Reorder Color Roles')
			return role

	@commands.command(aliases=['addcolours'])
	@commands.guild_only()
	@commands.cooldown(1, 300, commands.BucketType.guild)
	@checks.admin_or_perm(manage_roles=True)
	async def addcolors(self, ctx):
		"""Add color roles to current guild"""
		permissions = discord.Permissions.none()
		await self.create_role(ctx.guild, permissions=permissions, name='red', color=discord.Colour.red())
		await self.create_role(ctx.guild, permissions=permissions, name='green', color=discord.Colour.green())
		await self.create_role(ctx.guild, permissions=permissions, name='purple', color=discord.Colour.purple())
		await self.create_role(ctx.guild, permissions=permissions, name='blue', color=discord.Colour.blue())
		await self.create_role(ctx.guild, permissions=permissions, name='orange', color=discord.Colour.orange())
		await self.create_role(ctx.guild, permissions=permissions, name='black', color=discord.Colour(0x010101))
		await self.create_role(ctx.guild, permissions=permissions, name='white', color=discord.Colour(0xffffff))
		await self.create_role(ctx.guild, permissions=permissions, name='cyan', color=discord.Colour(0x08F8FC))
		await self.create_role(ctx.guild, permissions=permissions, name='lime', color=discord.Colour(0x00FF00))
		await self.create_role(ctx.guild, permissions=permissions, name='pink', color=discord.Colour(0xFF69B4))
		await self.create_role(ctx.guild, permissions=permissions, name='yellow', color=discord.Colour(0xFBF606))
		await self.create_role(ctx.guild, permissions=permissions, name='lightred', color=discord.Colour(0xFF4C4C))
		await self.create_role(ctx.guild, permissions=permissions, name='lavender', color=discord.Colour(0xD1D1FF))
		await self.create_role(ctx.guild, permissions=permissions, name='salmon', color=discord.Colour(0xFFA07A))
		await self.create_role(ctx.guild, permissions=permissions, name='darkblue', color=discord.Colour.dark_blue())
		await self.create_role(ctx.guild, permissions=permissions, name='darkpurple', color=discord.Colour.dark_purple())
		await self.create_role(ctx.guild, permissions=permissions, name='gold', color=discord.Colour.gold())
		await ctx.send("Added colors ({1})\n```{0}```".format(", ".join(COLOR_ROLES), len(COLOR_ROLES)))
		await ctx.send("You might need to re-order the new color ranks to the top of the roles\nif they are not working!")

	@commands.command(aliases=['removecolours'])
	@commands.guild_only()
	@commands.cooldown(1, 300, commands.BucketType.guild)
	@checks.admin_or_perm(manage_roles=True)
	async def removecolors(self, ctx):
		colors = await self.get_colors(ctx.guild)
		for color in colors:
			await color.delete(reason='remove all colors')
		await ctx.send(f"\N{WHITE HEAVY CHECK MARK} `Removed all color roles.`")

def setup(bot):
	bot.add_cog(Roles(bot))
