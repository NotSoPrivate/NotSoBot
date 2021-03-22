from discord.ext import commands
from mods.cog import Cog


class PlaceHolder(Cog):

	@commands.group()
	@commands.cooldown(2, 3, commands.BucketType.guild)
	async def phone(self, ctx):
		if ctx.guild and ctx.guild.get_member(336961510276595722):
			return
		await ctx.send("\N{WARNING SIGN} NotSoPhone is not here!\n" \
									 "Invite it at https://notsophone.com/invite\n" \
									 "\N{SMILING FACE WITH OPEN MOUTH} - *yes it's an actual phone*")

	@phone.command(name='call', aliases=['c'])
	async def phone_call(self, ctx):
		pass

	@phone.command(name='invite', aliases=['i'])
	async def phone_invite(self, ctx):
		pass

	@phone.command(name='lookup')
	async def phone_lookup(self, ctx):
		pass

	@phone.command(name='help')
	async def phone_help(self, ctx):
		pass

	@phone.command(name='balance', aliases=['b'])
	async def phone_balance(self, ctx):
		pass

	@phone.command(name='deposit')
	async def phone_deposit(self, ctx):
		pass

	@phone.command(name='rates')
	async def phone_rates(self, ctx):
		pass


def setup(bot):
	bot.add_cog(PlaceHolder(bot))
