from discord.ext import commands


class Cog(commands.Cog):
	def __init__(self, bot):
		self._bot = bot
		self.cursor = bot.mysql.cursor

	@property
	def bot(self):
		return self._bot

	@classmethod
	def setup(cls, bot):
		bot.add_cog(cls(bot))
