import discord
from discord.ext import commands

from mods.cog import Cog
from utils import cache

class Afk(Cog):

	@cache.cache()
	async def is_afk(self, user):
		q = await self.cursor.execute(f'SELECT user FROM `afk` WHERE user={user}')
		if await q.fetchone():
			return True

	async def remove_afk(self, id):
		self.is_afk.invalidate(self, id)

		sql = f'DELETE FROM `afk` WHERE user={id}'
		await self.cursor.execute(sql)

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def afk(self, ctx, *, reason:str=None):
		self.is_afk.invalidate(self, ctx.author.id)

		sql = 'INSERT INTO `afk` (`user`, `reason`) VALUES (%s, %s)'
		try:
			await self.cursor.execute(sql, (ctx.author.id, reason))
		except:
			await self.remove_afk(ctx.author.id)
			await ctx.send('\N{NO ENTRY} You are already afk, you have been removed.')
		else:
			msg = '\N{WHITE HEAVY CHECK MARK} `{0}` is now afk.'.format(ctx.author)
			await ctx.send(msg)

	async def check(self, user, channel):
		uid = user.id
		if isinstance(channel, discord.TextChannel) and await self.is_afk(uid):
			await self.remove_afk(uid)
			try:
				await user.send(f'\N{OK HAND SIGN} Welcome back, your AFK status has been removed ({channel.mention}).')
			except:
				pass
			return True

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.author == self.bot.user or message.author.bot:
			return
		elif message.guild is None:
			return
		elif await self.check(message.author, message.channel):
			return
		mentions = message.mentions
		if not mentions:
			return
		for m in mentions:
			q = await self.cursor.execute(f'SELECT * FROM `afk` WHERE user={m.id}')
			result = await q.fetchone()
			if not result:
				continue
			r = result['reason']
			r = f"\n{r}" if r else '.'
			try:
				await message.channel.send(f'\n:keyboard: `{m}` is currently AFK{r}')
			except (discord.Forbidden, discord.NotFound):
				await self.remove_afk(m.id)


def setup(bot):
	if not bot.self_bot:
		bot.add_cog(Afk(bot))
