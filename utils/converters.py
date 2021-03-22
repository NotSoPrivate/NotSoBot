from discord.ext import commands
from discord.utils import get

class MemberConverter(commands.converter.IDConverter):
	async def convert(self, ctx, argument):
		result = await ctx.bot.funcs.find_member(ctx.message, argument)
		if result is None:
			raise commands.BadArgument('Member "{0}" not found'.format(argument))
		return result

class MemberOrInt(MemberConverter):
	async def convert(self, ctx, argument):
		arg = str(argument)
		if arg.isdigit() and len(arg) < 15:
			return int(arg)
		return await super().convert(ctx, argument)

class MemberOrMessage(MemberConverter):
	async def convert(self, ctx, argument):
		arg = str(argument)
		if arg.isdigit() and ctx.bot.funcs.is_id(arg):
			try:
				return await ctx.channel.fetch_message(int(arg))
			except:
				pass
		return await super().convert(ctx, argument)

class GuildConverter(commands.converter.Converter):
	def convert(self, ctx, argument):
		if ctx.bot.funcs.is_id(argument):
			guild = ctx.bot.get_guild(int(argument))
		else:
			guild = get(ctx.bot.guilds, name=argument)
		if not guild:
			raise commands.BadArgument('Guild "{0}" not found'.format(argument))
		return guild

def setup_converters():
	commands.converter.MemberConverter = commands.converter.UserConverter = MemberConverter
	commands.converter.MemberOrInt = MemberOrInt
	commands.converter.MemberOrMessage = MemberOrMessage
	commands.converter.GuildConverter = GuildConverter
