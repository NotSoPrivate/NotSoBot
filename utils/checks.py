import json
import os

import discord.utils
from discord.ext import commands


class No_Perms(commands.CommandError): pass
class No_Role(commands.CommandError): pass
class No_Admin(commands.CommandError): pass
class No_Mod(commands.CommandError): pass
class Nsfw(commands.CommandError): pass
class No_BotPerms(commands.CommandError): pass
class No_DevServer(commands.CommandError): pass
class No_Ids(commands.CommandError): pass

def role_or_perm(t, ctx, role_predicate, check_channel_perms, **perms):
	if ctx.author.id in ctx.bot.owner_ids:
		return True
	if check_channel_perms:
		resolved = ctx.channel.permissions_for(ctx.author)
		if all(getattr(resolved, name, None) == value for name, value in perms.items()):
			return True
	if ctx.guild is None:
		return False
	role = discord.utils.find(role_predicate, ctx.author.roles)
	if role is not None:
		return True
	if t:
		return False
	else:
		raise No_Role()

# def role_or_perm(t, ctx, check, **perms):
#   if check_channel_permissions(ctx, perms):
#     return True
#   ch = ctx.message.channel
#   author = ctx.message.author
#   if ch.is_private:
#     return False
#   role = discord.utils.find(check, author.roles)
#   if role is not None:
#     return True
#   if t == 0:
#     raise No_Mod()
#   elif t == 1:
#     raise No_Admin()
#   else:
#     raise No_Role()

admin_perms = ('administrator',)
mod_perms = ('manage_messages', 'ban_members', 'kick_members')

mod_roles = ('mod', 'moderator')
def mod_or_perm(check_channel_perms=True, **perms):
	def predicate(ctx):
		if ctx.guild is None:
			return True
		if role_or_perm(True, ctx, lambda r: r.name.lower() in mod_roles, check_channel_perms, **perms):
			return True
		for role in ctx.author.roles:
			role_perms = []
			for s in role.permissions:
				role_perms.append(s)
			for s in role_perms:
				for x in mod_perms:
					if s[0] == x and s[1]:
						return True
				for x in admin_perms:
					if s[0] == x and s[1]:
						return True
		raise No_Mod()
	return commands.check(predicate)

admin_roles = ('admin', 'administrator', 'owner', 'bot admin')
def admin_or_perm(check_channel_perms=True, **perms):
	def predicate(ctx):
		if ctx.guild is None:
			return True
		if role_or_perm(True, ctx, lambda r: r.name.lower() in admin_roles, check_channel_perms, **perms):
			return True
		for role in ctx.author.roles:
			role_perms = []
			for s in role.permissions:
				role_perms.append(s)
			for s in role_perms:
				for x in admin_perms:
					if s[0] == x and s[1]:
						return True
		raise No_Admin()
	return commands.check(predicate)

def nsfw():
	def predicate(ctx):
		if ctx.guild is None or ctx.channel.is_nsfw():
			return True
		raise Nsfw()
	return commands.check(predicate)

def bot_has_perms(**perms):
	def predicate(ctx):
		permissions = ctx.channel.permissions_for(ctx.me)
		if all(getattr(permissions, perm, None) == value for perm, value in perms.items()):
			return True
		raise No_BotPerms(', '.join(perms.keys()))
	return commands.check(predicate)

def DevServer():
	def predicate(ctx):
		if ctx.guild and ctx.guild.id == 178313653177548800:
			return True
		raise No_DevServer()
	return commands.check(predicate)

def owner_or_ids(*ids):
	async def predicate(ctx):
		a = ctx.author
		if a.id in ids or await ctx.bot.is_owner(a):
			return True
		raise No_Ids(', '.join(map(str, ids)))
	return commands.check(predicate)
