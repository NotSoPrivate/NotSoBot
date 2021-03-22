import asyncio
import json
import logging
import sys
import time

import discord
from discord.ext import commands

import aioredis
from aioredis.errors import ConnectionForcedCloseError

from manager import shard_chunker
from mods.cog import Cog
from tabulate import tabulate
from utils.funcs import LimitedDict
from utils.time import human_timedelta


log = logging.getLogger('__main__')

SHARDS = shard_chunker()


class RPC(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		bot.rpc = self
		bot.get_id = self.get_id

		self.run_process = bot.funcs.run_process
		self.channel = 'notsobot.rpc' if not self.bot.dev_mode else 'notsodev.rpc'
		self.loaded = asyncio.Event(loop=bot.loop)
		self.received = LimitedDict(maxlen=20)
		self.timeout = 2
		self.ignore = ('presence_update',)
		self.ids = [tuple(x) for x in SHARDS]
		self.last_message = time.perf_counter()

		bot.loop.create_task(self.pubsub_init())


	def cog_unload(self):
		self.keepalive_task.cancel()
		self.reader.cancel()

		self.ch.close()
		self.pool.close()


	async def pubsub_init(self):
		# Create_redis_pool has reconnect
		self.pool = pool = await aioredis.create_redis_pool(
				('192.168.15.16', 6379), db=0, password="szHx6cskwZGXg62J", maxsize=3)
		self.loaded.set()
		self.ch = (await pool.subscribe(self.channel))[0]
		self.reader = self.bot.loop.create_task(self.channel_reader())
		self.keepalive_task = self.bot.loop.create_task(self.channel_keepalive())


	async def channel_reader(self):
		ch = self.ch
		try:
			while await ch.wait_message():
				msg = await ch.get(encoding='utf-8', decoder=json.loads)
				self.last_message = time.perf_counter()
				self.bot.dispatch('rpc_receive', msg)
		except Exception as e:
			log.exception('RPC channel reader error', exc_info=e)
			try:
				ch.close()
			except:
				pass


	async def channel_keepalive(self):
		await self.loaded.wait()
		log.redis('Starting RPC channel keepalive')
		while True:
			# Check if the channel is inactive
			# Also check if the last message was received over 60 seconds ago
			# Sometimes it bugs out and says it's active when it's actually not
			# so it's probably inactive if it hasn't received anything in >300 seconds/5 minutes
			if not self.ch or not self.ch.is_active or \
				(not self.bot.dev_mode and time.perf_counter() - self.last_message > 300):
				try:
					log.redis('RPC channel is inactive, reloading...')
					await asyncio.sleep(1)
					try:
						self.ch.close()
					except Exception:
						pass
					try:
						await self.pool.unsubscribe(self.channel)
					except Exception:
						pass
					self.ch = (await self.pool.subscribe(self.channel))[0]
					if self.ch.is_active:
						self.last_message = time.perf_counter()
					self.reader.cancel()
					self.reader = self.bot.loop.create_task(self.channel_reader())
				except asyncio.CancelledError:
					return
				except Exception as e:
					log.exception('Failed to reload inactive RPC channel', exc_info=e)
			await asyncio.sleep(10)


	async def publish(self, payload, snowflake, default_enc=None):
		await self.loaded.wait()
		try:
			await self.pool.publish(self.channel,
															json.dumps({
																'id': self.get_id(),
																'snowflake': snowflake,
																'payload': payload
															}, default=default_enc))
		except ConnectionForcedCloseError:
			return


	def reload_mod(self, mod):
		mod = f"mods.{mod}"
		self.bot.reload_extension(mod)


	async def reload_funcs(self):
		return await self.bot.get_cog('Debug').reload_funcs()


	@commands.Cog.listener()
	async def on_rpc_receive(self, data):
		try:
			payload = data.get('payload')
			snowflake = data.get('snowflake')
			if payload:
				cmd = payload.get('command')
				if cmd in self.ignore:
					return
				if cmd == 'received':
					if snowflake in self.received:
						fut = self.received[snowflake][data['id']]
						if not fut.done():
							fut.set_result(payload.get('response'))
					return
				try:
					func = getattr(self, f"cmd_{cmd}")
				except AttributeError:
					return
				call = func(payload) if func.__code__.co_argcount > 1 else func()
				r = await call if asyncio.iscoroutinefunction(func) else call
			await self.publish({
				'command': 'received',
				'response': r if payload else None
			}, data['snowflake'])
		except:
			if 0 in self.bot.shard_ids:
				raise

	#Commands

	def cmd_ping(self):
		return self.ping()


	def cmd_load_mod(self, payload):
		self.bot.load_extension(payload['mod'])


	def cmd_unload_mod(self, payload):
		self.bot.unload_extension(payload['mod'])


	async def cmd_reload_mod(self, payload):
		mod = payload['mod']
		if mod == 'funcs':
			await self.reload_funcs()
		elif mod == 'all':
			for i, m in enumerate(tuple(self.bot.cogs)):
				if i == 0:
					await self.reload_funcs()
				elif m not in ('Funcs', 'RPC', 'MySQLAdapter'):
					self.reload_mod(m)
		else:
			self.reload_mod(mod)


	async def cmd_send_message(self, payload):
		await self.bot.send_message(discord.Object(id=payload['channel_id']), payload['content'])


	async def cmd_eval(self, payload):
		if 'shard' not in payload or payload['shard'] == self.get_id():
			return await self.bot.funcs.repl(payload['code'])


	def cmd_stats(self):
		return [
			len(self.bot.guilds),
			sum(g.member_count for g in self.bot.guilds if not g.unavailable),
			self.ping(),
			human_timedelta(self.bot.last_message)
		]


	def cmd_set(self, payload):
		setattr(self, payload['name'], payload['value'])


	async def cmd_mysql_reload(self, payload):
		await self.bot.mysql.process_table(payload['table'])


	def cmd_seen_on(self, payload):
		guild = payload['guild']
		user = payload['user']
		return [member.guild.name for member in self.bot.get_all_members() \
						if member.id == user and member.guild.id != guild]


	def cmd_playing(self, payload):
		game = payload['game']
		return [member.id for member in self.bot.get_all_members() \
						if member.activity and member.activity.name == game]


	async def cmd_status(self, payload):
		await self.bot.change_presence(activity=discord.Game(name=payload['status']))


	async def cmd_update(self):
		await self.bot.funcs.git_update()


	#Coro Queue
	async def cmd_cq_reaction_add(self, payload):
		if 0 not in self.bot.shard_ids:
			return
		del payload['command']
		coro = self.bot.http.add_reaction(**payload)
		await self.bot.funcs.reaction_queue.put(coro)


	async def cmd_cq_reaction_remove(self, payload):
		if 0 not in self.bot.shard_ids:
			return
		del payload['command']
		coro = self.bot.http.remove_reaction(**payload)
		await self.bot.funcs.reaction_queue.put(coro)


	# Requires "shards" key
	async def cmd_debug(self, payload):
		if str(self.get_id()) in payload['shards']:
			vi = sys.version_info
			v = f"{vi[0]}.{vi[1]}"
			await self.run_process(
				[f"pip{v}", "install", "ptvsd"],
				shell=True
			)

			self.bot.get_cog("Debug") \
			.enable_debug(payload['wait'])


	async def wait_for(self, snowflake, i:int):
		await self.received[snowflake][i]
		return [i, self.received[snowflake][i].result() or True]


	async def wait(self, snowflake, timeout):
		if timeout is None or self.timeout > timeout:
			timeout = self.timeout
		futs = [asyncio.wait_for(self.wait_for(snowflake, i), timeout=timeout)
						for i in range(len(SHARDS))]
		fut = asyncio.gather(*futs, return_exceptions=True)
		await fut
		result = fut.result()
		results = {}
		for x in result:
			if isinstance(x, Exception):
				results[result.index(x)] = x
			else:
				results[x[0]] = x[1]
		return results


	async def send_command(self, command, snowflake, count=True, timeout=None, **payload):
		payload['command'] = command
		self.received[snowflake] = {i: asyncio.Future(loop=self.bot.loop) for i in range(len(SHARDS))}
		await self.publish(payload, snowflake)
		result = await self.wait(snowflake, timeout)
		if count:
			return f'{sum(1 for x in result.values() if x is True)}/{len(SHARDS)}'
		return result


	def ping(self):
		return '%.02f' % (self.bot.latency * 1000)


	async def seen_on(self, snowflake, shards=False, **kwargs):
		result = await self.send_command('seen_on', snowflake, count=False, **kwargs)
		guilds = []
		for shard, gl in result.items():
			if isinstance(gl, list):
				if shards:
					gl = [f"{g} - `{shard}`" for g in gl]
				guilds.extend(gl)
		return guilds


	async def playing(self, snowflake, game):
		result = await self.send_command('playing', snowflake, count=False, game=game)
		members = set()
		for x in result.values():
			if isinstance(x, list):
				for _ in x: members.add(_)
		return len(members)


	def get_id(self, shard:int=None):
		if self.bot.dev_mode:
			return 0
		elif shard:
			return self.ids[shard]
		return self.ids.index(self.bot.shard_ids)


	@commands.group()
	async def rpc(self, ctx):
		pass


	@rpc.command(name='load')
	@commands.is_owner()
	async def rpc_load(self, ctx, mod:str):
		mod = f'mods.{mod}'
		count = await self.send_command('load_mod', ctx.message.id, mod=mod)
		await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Loaded `{mod}` on **{count}** shards.')


	@rpc.command(name='unload')
	@commands.is_owner()
	async def rpc_unload(self, ctx, mod:str):
		mod = f'mods.{mod}'
		count = await self.send_command('unload_mod', ctx.message.id, mod=mod)
		await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Unloaded `{mod}` on **{count}** shards.')


	@rpc.command(name='reload')
	@commands.is_owner()
	async def rpc_reload(self, ctx, mod:str):
		count = await self.send_command('reload_mod', ctx.message.id, mod=mod, timeout=10)
		await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Reloaded `{mod}` on **{count}** shards.')


	@rpc.command(name='say')
	@commands.is_owner()
	async def rpc_say(self, ctx, channel_id:str, *, content:str):
		count = await self.send_command('send_message', ctx.message.id,
																		channel_id=channel_id, content=content)
		await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Sent message on **{count}** shards.')


	@rpc.group(name='eval', invoke_without_command=True)
	@commands.is_owner()
	async def rpc_eval(self, ctx, *, code:str):
		result = await self.send_command('eval', ctx.message.id, count=False, code=code)
		await ctx.send(self.bot.funcs.format_code(str(result)))

	@rpc_eval.command(name='shard')
	@commands.is_owner()
	async def rpc_eval_shard(self, ctx, shard:int, *, code:str):
		result = await self.send_command('eval', ctx.message.id, count=False, shard=shard, code=code)
		await ctx.send(self.bot.funcs.format_code(str(result[shard])))


	@commands.command()
	@commands.cooldown(1, 5)
	async def shards(self, ctx):
		result = await self.send_command('stats', ctx.message.id, count=False)
		headers = ('S', 'G', '~M', 'P', 'LM')
		table = []
		for r in result.keys():
			if isinstance(result[r], Exception):
				result[r] = ['Shard Error']
				result[r].extend([None for x in range(len(headers) - 1)])
			table.append([r, *result[r]])
		mean_ping = round(sum(float(result[x][2]) for x in result
											if result[x][2]) / sum(1 for x in result if result[x][-1]), 2)
		total_guilds, total_members = sum(int(result[x][0]) for x in result
																			if isinstance(result[x][0], int)), sum(int(result[x][1])
																			for x in result if result[x][1])
		table.append([
			'T', total_guilds,
			total_members,
			mean_ping,
			None
		])
		msg = f'Current Shard: {self.get_id()}\n{tabulate(table, headers=headers)}'
		await ctx.send(self.bot.funcs.format_code(msg))


	@rpc.command(name='ping')
	@commands.cooldown(1, 5)
	async def rpc_ping(self, ctx):
		result = await self.send_command('ping', ctx.message.id, count=False)
		table = []
		headers = ['Shard', 'Ping']
		for r in result.keys():
			table.append([r, f'{result[r]} ms' if not isinstance(result[r], Exception) else 'Shard Error'])
		await ctx.send(self.bot.funcs.format_code(tabulate(table, headers=headers)))


	@rpc.command(name='timeout')
	@commands.is_owner()
	async def rpc_timeout(self, ctx, timeout:float=None):
		if timeout is None:
			await ctx.send(f'\N{INFORMATION SOURCE} RPC Timeout: `{self.timeout}` seconds.')
		else:
			count = await self.send_command('set', ctx.message.id, count=True, name='timeout', value=timeout)
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Set RPC Timeout to: ' \
										 f'`{timeout}` seconds on {count} shards.')


	@rpc.group(name='mysql')
	@commands.is_owner()
	async def rpc_mysql(self, ctx):
		pass

	@rpc_mysql.command(name='reload')
	@commands.is_owner()
	async def rpc_mysql_reload(self, ctx, table):
		count = await self.send_command('mysql_reload', ctx.message.id,
																		count=True, timeout=10, table=table)
		await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Reloaded MySQL Table `{table}` on {count} shards.')


	@rpc.command(name='update')
	@commands.is_owner()
	async def rpc_update(self, ctx):
		count = await self.send_command('update', ctx.message.id, count=True, timeout=10)
		await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Git Pulled on `{count}` shards.')


	@rpc.command(name='debug')
	@commands.is_owner()
	async def rpc_debug(self, ctx, *shards):
		if not shards:
			return await ctx.send("what shard(s)")

		wait = shards[0] == "wait"
		if wait:
			shards = shards[1:]

		shards = await self.send_command('debug', ctx.message.id, timeout=30,
																		count=False, shards=list(shards), wait=wait)
		await ctx.send(
			f"\N{WHITE HEAVY CHECK MARK} Enabled debug on shards " \
			f'`{", ".join(x for x in shards if shards[x])}`.'
		)


def setup(bot):
	if not bot.self_bot:
		bot.add_cog(RPC(bot))
