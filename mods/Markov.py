import discord
import re
from discord.ext import commands
from mods.cog import Cog
from utils import checks

class MarkovGen:
	def __init__(self, cursor):
		self.cursor = cursor
		self.sql = "SELECT * FROM `markov` WHERE (message LIKE %s OR message LIKE %s) ORDER BY RAND() LIMIT 1"
		self.regex = re.compile(r'\s+')

	async def learn(self, message):
		content = self.regex.sub(' ', message.content.strip())
		await self.cursor.execute('INSERT INTO `markov` (`user`, `name`, `message`) VALUES (%s, %s, %s)', \
														 (message.author.id, message.author.name, content))

	def get_words(self, sentence:str):
		if re.match(r'^\s*$', sentence):
			return []
		return self.regex.split(sentence)

	def get_chain(self, words:list, depth:int=2):
		out = []
		for i in range(depth):
			try:
				out.append(words[len(words) - depth + i])
			except IndexError:
				break
		return out

	def match_chain(self, words:list, chain:list, depth:int=2):
		out = []
		for i in range(len(words)):
			word = words[i]
			if not chain or word == chain[0]:
				acceptable = True
				for i2 in range(len(chain)):
					if chain[i2] != words[i + i2]:
						acceptable = False
						break
				if acceptable:
					if len(chain) < depth:
						for i2 in range(i, min(i + depth, len(words))):
							out.append(words[i2])
					else:
						for i2 in range(1, len(chain)):
							out.append(chain[i2])
						try:
							out.append(words[i + len(chain)])
						except IndexError:
							pass
					break
		return out

	async def query(self, chain:list):
		sentence = " ".join(chain)
		if sentence.strip() == "":
			q = await self.cursor.execute('SELECT * FROM `markov` ORDER BY RAND() LIMIT 1')
			return await q.fetchone()
		q = await self.cursor.execute(self.sql, (f"% {sentence} %", f"{sentence} %"))
		return await q.fetchone()

	async def generate(self, depth:int=2, maxlen:int=50, sentence:str=""):
		if sentence:
			words = self.get_words(sentence)
			chain = self.get_chain(words, depth)
		else:
			words = chain = []
		out = words[:]
		last_chain = None
		while len(out) < maxlen:
			data = await self.query(chain)
			if not data or not data['message']:
				break
			words = self.get_words(data['message'])
			last_chain = chain[:]
			chain = self.match_chain(words, chain, depth)
			if ((len(chain) - len(last_chain)) <= 0) and len(chain) < depth:
				break
			elif len(last_chain) < depth:
				for i in range(len(last_chain), len(chain) - 1):
					out.append(chain[i])
			else:
				out.append(chain[len(chain) - 1])
		return " ".join(out)

guilds = (178313653177548800,)

def can_run_markov():
	def predicate(ctx):
		return ctx.guild.id in guilds
	return commands.check(predicate)

class Markov(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.cache = {}
		self.files_path = bot.path.files
		self.users = {}
		self.ignore_channels = (178313681786896384, 211247117816168449, 180073721048989696)
		self.prefixes = ('!', '.', '!!', '`', '-', '=', ',', '/', '?')
		self.model = MarkovGen(bot.mysql.cursor)

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None:
			return
		elif message.channel.id in self.ignore_channels:
			return
		elif message.content == "":
			return
		elif message.author.bot or message.content.startswith(self.prefixes):
			return
		if message.guild.id in guilds:
			await self.model.learn(message)
		# if message.author.id in self.users.keys() and self.users[message.author.id] == message.guild.id:
		# 	path = self.files_path('markov/{0}_{1}/'.format(message.author.id, message.guild.id))
		# 	await self.add_markov(path, message.clean_content)

	@commands.group(aliases=['mark'], invoke_without_command=True)
	@commands.guild_only()
	@can_run_markov()
	async def markov(self, ctx, *, text:str=" "):
		depth = 2
		sp = text.split()
		if len(sp) > 1 and sp[0].isdigit():
			depth = int(sp[0])
			if depth > 9:
				depth = 9
			elif depth < 1:
				depth = 1
			text = ' '.join(sp[1:]).strip()
		m = await self.model.generate(depth, 200, text)
		if not m:
			await ctx.send('\N{WARNING SIGN} `Markov generation failed (Try again?).`')
		else:
			await ctx.send(m, replace_mentions=True, replace_mentions_limit=1)

	async def get_messages(self, channel, message_id, limit, reverse, user=None):
		m = await channel.fetch_message(int(message_id))
		if reverse:
			after = m
			before = None
		else:
			before = m
			after = None
		msgs = []
		async for message in channel.history(limit=limit, before=before, after=after):
			if user and message.author.id != user.id:
				continue
			elif message.author.bot or message.content.startswith(self.prefixes):
				continue
			msgs.append(message)
		return msgs

	@markov.group(name='generate', invoke_without_command=True)
	@commands.is_owner()
	async def markov_generate(self, ctx, message_id:str, limit:int=5000, reverse:bool=False):
		_x = await ctx.send('ok, this ~~might~~ will take a while')
		await _x.edit(content='Fetching messages.')
		msgs = await self.get_messages(ctx.channel, message_id, limit, reverse)
		await _x.edit(content='Learning...')
		for msg in msgs:
			await self.model.learn(msg)
		await _x.edit(content='\N{WHITE HEAVY CHECK MARK} Done.')

	# @markov_generate.command(name='user')
	# @commands.is_owner()
	# async def markov_generate_user(self, ctx, user:discord.User, message_id:str, limit:int=5000, reverse:bool=False):
	# 	_x = await ctx.send('ok, this ~~might~~ will take a while')
	# 	markov_path = self.files_path(f'markov/{ctx.author.id}_{ctx.guild.id}/')
	# 	code_path = self.files_path('markov/generated/{0}.js'.format(user.name.lower()))
	# 	await self.bot.edit_message(_x, 'Fetching messages.')
	# 	msgs = await self.get_messages(ctx.channel, message_id, limit, reverse, user)
	# 	await self.bot.edit_message(_x, 'Generating code.')
	# 	self.generate_code(markov_path, code_path, msgs)
	# 	await self.bot.edit_message(_x, '\N{WHITE HEAVY CHECK MARK} Done, `{0}`'.format(code_path))

def setup(bot):
	bot.add_cog(Markov(bot))