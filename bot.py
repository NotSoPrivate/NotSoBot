import asyncio
import contextlib
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from time import time as now

import ujson as json

import discord
from discord.ext import commands

# from ttldict import TTLOrderedDict
from utils.cache import TTLDict
from utils.funcs import get_prefix, create_activity

# Patch ujson
from discord import gateway
gateway.json = json

try:
	import uvloop
	asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except:
	pass

class NotSoBase(commands.bot.BotBase):
	def __init__(self, *args, **kwargs):
		self.loop = kwargs.pop('loop', asyncio.get_event_loop())
		self.executor = ThreadPoolExecutor(max_workers=1)

		self.loop.set_default_executor(self.executor)

		# If uvloop doesn't exist
		try:
			asyncio.get_child_watcher().attach_loop(self.loop)
		except NotImplementedError:
			pass

		self.dev_mode = kwargs.pop('dev_mode', False)
		self.self_bot = kwargs.get('self_bot', False)

		super().__init__(*args, **kwargs)

		self.command_messages = TTLDict(1200)

		self.remove_command('help')

		self.load_extension('utils.mysql')
		self.load_extension('utils.funcs')

		self.load_extension('mods.RPC')

		# Metrics - add hooks ASAP
		self.load_extension('mods.Metrics')
		self.load_extension('mods.Web')

		self.loop.create_task(self._load())

		self.start_time = now()
		self.last_message = None
		self.guild_id = 178313653177548800

	def __repr__(self):
		return f'<NotSoBot shard: {self.shard_ids}, shard_count: ' \
					 f'{self.shard_count}, commands: {len(self.commands)}>'

	async def login(self, *args, **kwargs):
		tokens = json.loads(os.environ.get('TOKENS'))
		if self.self_bot:
			token = tokens['bot_self']
		elif self.dev_mode:
			token = tokens['bot_dev']
		else:
			token = tokens['bot']
		return await super().login(token, bot=not self.self_bot)

	@contextlib.contextmanager
	def setup_logging(self):
		try:
			logging.getLogger('discord').setLevel(logging.INFO)
			logging.getLogger('discord.http').setLevel(logging.WARNING)
			log = logging.getLogger()
			log.setLevel(logging.INFO)
			base = 'bot' if not self.dev_mode else 'dev'
			handler = logging.FileHandler(
				filename=f'/logs/{base}{self.get_id()}.log', encoding='utf-8', mode='w')
			dt_fmt = '%Y-%m-%d %H:%M:%S'
			fmt = logging.Formatter('[{asctime}] [{levelname:<7}] {name}: {message}', dt_fmt, style='{')
			handler.setFormatter(fmt)
			log.addHandler(handler)
			yield
		finally:
			handlers = log.handlers[:]
			for hdlr in handlers:
				hdlr.close()
				log.removeHandler(hdlr)

	async def _load(self):
		# Wait for Redis Pool
		await self.rpc.loaded.wait()

		self.load_extension('mods.Core')

		# Defined in Core - prevent double reload in .reload all
		await self.load_modules()

	async def is_owner(self, user):
		extras = (
			61189081970774016, # Spencer#0001
			300505364032389122 # cake#0001
		)
		if user.id in extras:
			return True
		return await super().is_owner(user)

class NotSoBot(NotSoBase, discord.AutoShardedClient):
	pass

class NotSoSelf(NotSoBase, discord.Client):
	pass


#set before any init
discord.member.create_activity = create_activity


if __name__ == "__main__":
	dev_mode = os.getenv('dev_mode') in ('1', 'true')
	self_bot = sys.argv[1] == 'selfbot'
	shard_ids = sys.argv[1] if not self_bot else None
	shard_count = int(sys.argv[2]) if not self_bot else None

	loop = asyncio.get_event_loop()
	mentions = discord.AllowedMentions(everyone=False)
	BASE = NotSoSelf if self_bot else NotSoBot
	bot = BASE(loop=loop, shard_ids=tuple(map(int, shard_ids.split(','))) if not self_bot else None,
						 shard_count=shard_count, dev_mode=dev_mode,
						 self_bot=self_bot, max_messages=10000,
						 fetch_offline_members=False,
						 command_prefix=get_prefix,
						 guild_subscriptions=dev_mode or self_bot,
						 allowed_mentions=mentions)

	try:
		with bot.setup_logging():
			bot.run()
	except KeyboardInterrupt:
		pass
	finally:
		print('\nKeyboardInterrupt - Shutting down...')
		bot.executor.shutdown(wait=True)
