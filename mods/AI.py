# import discord
# import asyncio
# import re
from discord.ext import commands
# from chatterbot import ChatBot
from mods.cog import Cog
from utils import checks

# chatbot = ChatBot("NotSoBot",
# 									trainer='chatterbot.trainers.ChatterBotCorpusTrainer',
# 									storage_adapter="chatterbot.storage.MongoDatabaseAdapter",
# 									output_format='text',
# 									database='chatterbot-database',
# 									database_uri='mongodb://localhost:27017/')

class AI(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		# self.ai_target = {}
		self.get_json = bot.get_json
		self.cb_user, self.cb_key = ('DHorqbJ5r4kwaiv2', 'P2ZElJshMaPiz4agQOhZ4x5gfWd9JyKz')

	@commands.command(aliases=['cb'])
	async def cleverbot(self, ctx, *, txt:str):
		payload = {
			'text': txt, 
			'nick': 'NotSoBot', 
			'user': self.cb_user, 
			'key': self.cb_key
		}
		msg = await self.get_json('https://cleverbot.io/1.0/ask', data=payload)
		if msg and msg['status'] == 'success':
			await ctx.send(f":speech_balloon: {msg['response'][:1998]}")
		else:
			await ctx.send('\N{WARNING SIGN} `Cleverbot API request failed.`')

	# @commands.group(aliases=['talk'], invoke_without_command=True)
	# async def ai(self, ctx, *, msg:str=None):
	# 	"""Toggle AI Targeted Responses"""
	# 	if msg != None:
	# 		await self.bot.send_typing(ctx.channel)
	# 		ask_msg = ctx.message.content[:899]
	# 		r = chatbot.get_response(ask_msg).text
	# 		if len(r):
	# 			msg = "**{0.name}**\n{1}".format(ctx.author, r)
	# 			await ctx.send(msg)
	# 	elif ctx.author.id not in self.ai_target:
	# 		await ctx.send("ok, AI targetting user `{0}`\n".format(ctx.author.name))
	# 		self.ai_target.update({ctx.author.id:ctx.channel.id})
	# 	else:
	# 		await ctx.send("ok, removed AI target `{0}`".format(ctx.author.name))
	# 		del self.ai_target[ctx.author.id]

	# @ai.command(name='remove', aliases=['forceremove'])
	# @checks.mod_or_perm(manage_guild=True)
	# async def ai_remove(self, ctx, *users:discord.User):
	# 	for user in users:
	# 		if user.id in self.ai_target.keys():
	# 			del self.ai_target[user.id]
	# 			await ctx.send('\N{WHITE HEAVY CHECK MARK} Removed `{0}` from AI Target.'.format(user))
	# 		else:
	# 			await ctx.send('\N{WARNING SIGN} `{0}` is not in the AI Target!'.format(user))

	# async def on_message(self, message):
	# 	if not message.author.id in self.ai_target.keys():
	# 		return
	# 	elif self.ai_target[message.author.id] != message.channel.id:
	# 		return
	# 	if message.author == self.bot.user:
	# 		return
	# 	if message.content.startswith('.'):
	# 		return
	# 	check = await self.bot.funcs.command_check(message, 'off')
	# 	if check:
	# 		del self.ai_target[message.author.id]
	# 		return
	# 	ask_msg = message.clean_content[:899]
	# 	try:
	# 		await self.bot.send_typing(message.channel)
	# 		r = chatbot.get_response(ask_msg).text
	# 		if len(r):
	# 			msg = "**{0.name}**\n{1}".format(message.author, r)
	# 			await self.bot.send_message(message.channel, msg)
	# 	except:
	# 		if message.author.id in self.ai_target.keys():
	# 			del self.ai_target[message.author.id]
	# 	finally:
	# 		await asyncio.sleep(1)

def setup(bot):
	bot.add_cog(AI(bot))