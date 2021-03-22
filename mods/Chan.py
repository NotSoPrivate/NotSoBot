import random
from discord.ext import commands
from lxml.html import fromstring
from mods.cog import Cog

class Chan(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.get_json = bot.get_json
		self.boards = ['b', 'pol', 'v', 's4s']
		self.API = 'http://api.4chan.org/{0}/1.json'
		self.POST_URL = 'http://boards.4chan.org/{0}/res/{1}#p{2}'

	@classmethod
	def parse_post(cls, element):
		formatted_element = []
		text = [element.text, element.tail]
		if element.tag == 'br':
			text[0] = '\n'
		text = ' '.join(filter(lambda x: x, text))
		formatted_element.append(text)
		for child in element:
			formatted_child = cls.parse_post(child)
			formatted_element.append(formatted_child)
		text = ' '.join(formatted_element).strip()
		return text.replace(' +', ' ')

	async def get_post(self, board):
		'''Return all posts of the board's front page.'''
		load = await self.get_json(self.API.format(board))
		if not load:
			return False
		try:
			threads = map(lambda x: x['posts'], load['threads'])
		except:
			return False
		posts = []
		for thread in threads:
			op = thread[0]
			for post in thread:
				try:
					content = post['com']
				except KeyError:
					content = ''
				else:
					content = self.parse_post(fromstring(content))
				posts.append({
					'content': content,
					'url': self.POST_URL.format(board, op['no'], post['no']),
				})
		posts = list(filter(lambda x: x['content'] and len(x['content']) >= 20, posts))
		return random.choice(posts)['content']

	@commands.command(aliases=['4chan'])
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def chan(self, ctx, board:str=None):
		"""Replies random 4chan post."""
		try:
			if board is None:
				post = await self.get_post(random.choice(self.boards))
			else:
				post = await self.get_post(board.replace("/", "")) 
			assert post
		except:
			await ctx.send("Invalid Board!")
		else:
			await ctx.send(post)

def setup(bot):
	bot.add_cog(Chan(bot))
