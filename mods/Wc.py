import asyncio
import time

import discord
from discord.ext import commands

import ujson as json
from mods.cog import Cog

class WcLimit(Exception): pass

class Wc(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.bytes_download = bot.bytes_download
		self.get_images = bot.get_images
		self.sems = {}
		self.sem_cleaner_task = bot.loop.create_task(self.sem_cleaner())
		self.generic_api = bot.funcs.generic_api

	def cog_unload(self):
		self.sem_cleaner_task.cancel()

	async def sem_cleaner(self):
		while not self.bot.is_closed():
			for guild in list(self.sems):
				t = self.sems[guild][1]
				if round(time.time() - t) >= 300:
					del self.sems[guild]
			await asyncio.sleep(120)

	async def get_messages(self, channel, limit, user=None):
		msgs = []
		async for message in channel.history(limit=limit):
			if user is not None and user != message.author:
				continue
			msgs.append(message.clean_content)
		if not msgs:
			return 'no messages found rip'.split()
		final = []
		for msg in msgs:
			final.extend(x[:30] for x in msg.split())
		return final

	def check(self, ctx):
		sf = (ctx.guild or ctx.channel).id
		t = time.time()
		if sf not in self.sems:
			self.sems[sf] = [asyncio.BoundedSemaphore(value=2, loop=self.bot.loop), t]
		else:
			self.sems[sf][1] = t
		sem = self.sems[sf][0]
		if sem.locked():
			raise WcLimit
		return sem

	@commands.group(name='wc', aliases=['wordcloud', 'wordc'], invoke_without_command=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def wc(self, ctx, *urls:str):
		async with self.check(ctx):
			if ctx.message.channel_mentions:
				channel = ctx.message.channel_mentions[0]
				urls = " ".join(urls).replace(channel.mention, "").split()
			else:
				channel = ctx.channel
			if ctx.guild and not channel.permissions_for(ctx.author).read_messages:
				return await ctx.send('\N{NO ENTRY} `You do not have permission to message in that channel.`')
			max_messages = 500
			custom = 0
			if len(urls) == 1 and urls[0].isdigit():
				max_messages = int(urls[0])
			elif urls:
				get_images = await self.get_images(ctx, urls=urls, scale=4000)
				if not get_images:
					return
				custom = 1
				image, scale, _ = get_images
				url = image[0]
				if scale:
					max_messages = int(scale)
			if max_messages > 4000 or max_messages < 1:
				max_messages = 500
			x = await ctx.send("ok, processing{0}".format(' (this might take a while)' if max_messages > 2000 else ''))				
			text = await self.get_messages(channel, max_messages)
			messages = json.dumps({
				'm': text
			})
			b = await self.generic_api(ctx.command.name,
																	url if custom else None,
																	messages=messages, max_messages=max_messages,
																	custom=custom)
			await ctx.send(file=b, filename='wordcloud.png')
			await ctx.delete(x)

	@wc.command(name='user', aliases=['u'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def wc_user(self, ctx, user:discord.User, max_messages:int=500):
		async with self.check(ctx):
			channel = ctx.channel
			if max_messages > 4000 or max_messages < 1:
				max_messages = 500
			x = await ctx.send("ok, processing{0}".format(' (this might take a while)' if max_messages > 2000 else ''))				
			text = await self.get_messages(channel, max_messages, user=user)
			messages = json.dumps({
				'm': text
			})
			b = await self.generic_api('wc', None, messages=messages, max_messages=max_messages, custom=0)
			await ctx.send(file=b, filename='wordcloud.png')
			await ctx.delete(x)

	@wc.error
	@wc_user.error
	async def wc_error(self, ctx, error):
		if isinstance(error.__cause__, WcLimit):
			await ctx.send('\N{NO ENTRY} `Currently processing 2 wordclouds, please wait until one or more finishes.`')

def setup(bot):
	bot.add_cog(Wc(bot))
