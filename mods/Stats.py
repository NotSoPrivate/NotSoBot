from discord.ext import commands

from aioredis import PoolClosedError
from mods.cog import Cog
from utils.paginator import Pages


class Stats(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.pool = bot.rpc.pool

	@commands.Cog.listener()
	async def on_command(self, ctx):
		cmd = ctx.command.full_parent_name or ctx.command.name
		try:
			await self.pool.hincrby("cmd_stats", cmd)
		except PoolClosedError:
			pass

	@commands.command(aliases=['topcmds'])
	@commands.cooldown(1, 15, commands.BucketType.guild)
	async def stats(self, ctx):
		data = await self.pool.hgetall('cmd_stats', encoding='utf-8')
		data = {x: int(data[x]) for x in data}
		entries = [f"`{x}` - {int(data[x]):,}"
							 for x in sorted(data, reverse=True, key=data.get)]
		p = Pages(ctx, entries=entries, per_page=25, method=2)
		p.embed.title = '\N{KEYBOARD} Top Commands (Since 07/14/2018):'
		p.embed.color = 0x3498db
		await p.paginate()


def setup(bot):
	if not bot.self_bot:
		bot.add_cog(Stats(bot))
