# https://github.com/khazhyk/dango.py/blob/master/dango/plugins/metrics.py
# https://github.com/khazhyk/dango.py/blob/master/dango/plugins/latency.py

import time
from datetime import datetime
from enum import IntEnum

from aiohttp import web
from discord.ext import commands, tasks

import prometheus_client
from mods.cog import Cog
from prometheus_client import REGISTRY


OPCODE_NAMES = {
	0: "DISPATCH",
	1: "HEARTBEAT",
	2: "IDENTIFY",
	3: "PRESENCE",
	4: "VOICE_STATE",
	5: "VOICE_PING",
	6: "RESUME",
	7: "RECONNECT",
	8: "REQUEST_MEMBERS",
	9: "INVALIDATE_SESSION",
	10: "HELLO",
	11: "HEARTBEAT_ACK",
	12: "GUILD_SYNC",
}

DISPATCH_NAMES = (
	"READY",
	"RESUMED",
	"MESSAGE_ACK",
	"MESSAGE_CREATE",
	"MESSAGE_DELETE",
	"MESSAGE_DELETE_BULK",
	"MESSAGE_UPDATE",
	"MESSAGE_REACTION_ADD",
	"MESSAGE_REACTION_REMOVE_ALL",
	"MESSAGE_REACTION_REMOVE",
	"PRESENCE_UPDATE",
	"USER_UPDATE",
	"CHANNEL_DELETE",
	"CHANNEL_UPDATE",
	"CHANNEL_CREATE",
	"CHANNEL_PINS_ACK",
	"CHANNEL_PINS_UPDATE",
	"CHANNEL_RECIPIENT_ADD",
	"CHANNEL_RECIPIENT_REMOVE",
	"GUILD_INTEGRATIONS_UPDATE",
	"GUILD_MEMBER_ADD",
	"GUILD_MEMBER_REMOVE",
	"GUILD_MEMBER_UPDATE",
	"GUILD_EMOJIS_UPDATE",
	"GUILD_CREATE",
	"GUILD_SYNC",
	"GUILD_UPDATE",
	"GUILD_DELETE",
	"GUILD_BAN_ADD",
	"GUILD_BAN_REMOVE",
	"GUILD_ROLE_CREATE",
	"GUILD_ROLE_DELETE",
	"GUILD_ROLE_UPDATE",
	"GUILD_MEMBERS_CHUNK",
	"VOICE_STATE_UPDATE",
	"VOICE_SERVER_UPDATE",
	"WEBHOOKS_UPDATE",
	"TYPING_START",
	"RELATIONSHIP_ADD",
	"RELATIONSHIP_REMOVE",
)

def _opcode_name(opcode):
	return OPCODE_NAMES.get(opcode, opcode)


class ShardState(IntEnum):
	UNKNOWN = 0
	UNHEALTHY = 1
	OFFLINE = 2
	ONLINE = 3
	STARTING = 4
	STOPPING = 5
	RESUMING = 6


# pylint: disable=E1101

class Metrics(Cog):
	def __init__(self, bot):
		super().__init__(bot)

		self.get_id = bot.rpc.get_id
		self.post_data = bot.funcs.post_data

		# self.declare_metric(
		# 	"opcodes", prometheus_client.Counter,
		# 	'Opcodes', ['opcode']
		# )
		# self.declare_metric(
		# 	"dispatch_events", prometheus_client.Counter,
		# 	'Dispatch Events', ['event']
		# )
		# self.declare_metric(
		# 	"command_triggers", prometheus_client.Counter,
		# 	'Command Triggers', ['command']
		# )
		# self.declare_metric(
		# 	"command_completions", prometheus_client.Counter,
		# 	'Command Completions', ['command']
		# )
		# self.declare_metric(
		# 	"command_errors", prometheus_client.Counter,
		# 	'Command Errors', ['command', 'error']
		# )

		# buckets = (
		# 	0.001, 0.003, 0.006,
		# 	0.016, 0.039, 0.098,
		# 	0.244, 0.61, 1.526,
		# 	3.815, 9.537, 23.842,
		# 	59.605, 149.012, 372.529,
		# 	931.323, 2328.306
		# )
		# self.declare_metric(
		# 	"command_timing", prometheus_client.Histogram,
		# 	'Command Timing', ['command'], buckets=buckets
		# )

		# self.declare_metric(
		# 	"message_latency", prometheus_client.Summary,
		# 	'Message Latency', ['shard']
		# )

		# self.declare_metric(
		# 	"server_count", prometheus_client.Gauge, "Server Count",
		# 	function=lambda: len(self.bot.guilds)
		# )
		# self.declare_metric(
		# 	"ws_latency", prometheus_client.Gauge,
		# 	"Websocket Latency", ['shard']
		# )
		# self.ws_latency.labels(shard=self.get_id()).set_function(
		# 	lambda: round(self.bot.latency * 1000, 2)
		# )
		# self.declare_metric(
		# 	"server_members", prometheus_client.Gauge,
		# 	"Server Members", ['name', 'id']
		# )

		# loop = bot.loop
		# loop.create_task(self._init_servers())

		# for opcode in OPCODE_NAMES.values():
		# 	self.opcodes.labels(opcode=opcode)

		# for dispatch_name in DISPATCH_NAMES:
		# 	self.dispatch_events.labels(event=dispatch_name)

		# self._in_flight_ctx = {}
		# self._headers = {'Content-Type': prometheus_client.CONTENT_TYPE_LATEST}

		self.glance_api = "http://192.168.15.16:6969/api"
		self.glance_cluster = "main" if not bot.dev_mode else "dev"
		self.glance_key = "diggitydog"

		self.shard_states = {
			s: ShardState.OFFLINE for s in bot.shard_ids
		}
		self.unhealthy_states = (
			ShardState.STARTING,
			ShardState.RESUMING,
			ShardState.OFFLINE,
			ShardState.STOPPING
		)

		self.ready_counter = 0

		self._glance_health.start()


	def cog_unload(self):
		# from prometheus_client.metrics import MetricWrapperBase

		# for f in self.__dict__.values():
		# 	if isinstance(f, MetricWrapperBase):
		# 		REGISTRY.unregister(f)

		self._glance_health.cancel()


	# pylint: disable=W0212
	# @staticmethod
	# def get_prom(name):
	# 	try:
	# 		return REGISTRY._names_to_collectors[name]
	# 	except KeyError:
	# 		for key, value in REGISTRY._collector_to_names.items():
	# 			for val in value:
	# 				if val.startswith(name):
	# 					return key

	# 	raise KeyError

	# def declare_metric(self, name, mt, *args, function=None, **kwargs):
	# 	try:
	# 		setattr(self, name, mt(name, *args, **kwargs))
	# 	except ValueError:
	# 		setattr(self, name, self.get_prom(name))

	# 	if function:
	# 		getattr(self, name).set_function(function)


	# def _set_server(self, guild):
	# 	self.server_members.labels(
	# 		name=guild.name, id=guild.id
	# 	).set(guild.member_count)

	# async def _init_servers(self):
	# 	await self.bot.wait_until_ready()
	# 	for guild in self.bot.guilds:
	# 		self._set_server(guild)


	# @commands.Cog.listener()
	# async def on_guild_join(self, guild):
	# 	self._set_server(guild)

	# @commands.Cog.listener()
	# async def on_message(self, message):
	# 	if message.author == self.bot.user:
	# 		now = datetime.utcnow()
	# 		self.message_latency.labels(
	# 			shard=self.get_id()).observe(round(
	# 			(now - message.created_at).total_seconds() * 1000, 2)
	# 		)

	# @commands.Cog.listener()
	# async def on_socket_response(self, data):
	# 	opcode = data['op']
	# 	self.opcodes.labels(opcode=_opcode_name(opcode)).inc()

	# 	if opcode == 0:
	# 		self.dispatch_events.labels(event=data.get('t')).inc()

	# @commands.Cog.listener()
	# async def on_command(self, ctx):
	# 	self.command_triggers.labels(command=ctx.command.qualified_name).inc()
	# 	self._in_flight_ctx[ctx] = time.time()

	# @commands.Cog.listener()
	# async def on_command_completion(self, ctx):
	# 	qn = ctx.command.qualified_name
	# 	self.command_completions.labels(command=qn).inc()
	# 	self.command_timing.labels(command=qn).observe(
	# 		round(time.time() - self._in_flight_ctx[ctx], 2)
	# 	)
	# 	del self._in_flight_ctx[ctx]

	# @commands.Cog.listener()
	# async def on_command_error(self, ctx, error):
	# 	self.command_errors.labels(
	# 		command=ctx.command.qualified_name,
	# 		error=type(error)
	# 	).inc()
	# 	try:
	# 		del self._in_flight_ctx[ctx]
	# 	except KeyError:
	# 		pass


	# Glance

	@tasks.loop(seconds=15.0)
	async def _glance_health(self):
		if self.ready_counter < len(self.bot.shard_ids):
			return

		for (shard, state) in self.shard_states.items():
			if state not in self.unhealthy_states:
				await self.post_glance("health", shard=shard)

	async def post_glance(self, ep, shard, state:int=None):
		api = f"{self.glance_api}/{ep}/{self.glance_cluster}/{shard}"
		if state:
			api += f"/{state}"

		headers = {"Authorization": self.glance_key}

		await self.post_data(api, data=None, headers=headers)

	def set_state(self, shard, state):
		if shard is None:
			for s in self.shard_states:
				self.shard_states[s] = state
		else:
			self.shard_states[shard] = state


	# States which acquire lock
	# pls no race conditions

	# The interstate between WS connected and READY
	# lets set this as CONNECTING for glance

	@commands.Cog.listener()
	async def on_ws_connect(self, shard_id):
		state = ShardState.STARTING
		self.set_state(shard_id, state)

		await self.post_glance(
			"status", shard=shard_id, state=state
		)

	@commands.Cog.listener()
	async def on_resuming(self, shard_id):
		state = ShardState.RESUMING
		self.set_state(shard_id, state)

		await self.post_glance(
			"status", shard=shard_id, state=state
		)

	@commands.Cog.listener()
	async def on_disconnect(self, shard_id):
		# shard_id = None = full disconnect
		state = ShardState.OFFLINE
		self.set_state(shard_id, state)

		if shard_id is None:
			for s in self.bot.shard_ids:
				await self.post_glance("status", shard=s, state=state)
		else:
			await self.post_glance(
				"status", shard=shard_id, state=state
			)

	# SIGTERM HANDLER - DOCKER STOP
	# called in Core
	async def handle_stop(self):
		state = ShardState.STOPPING

		for s in self.bot.shard_ids:
			await self.post_glance(
				"status", shard=s, state=state
			)
			self.set_state(s, state)


	# States which release lock

	# READY event from GW
	@commands.Cog.listener()
	async def on_connect(self, shard_id):
		self.ready_counter += 1

		state = ShardState.ONLINE
		self.set_state(shard_id, state)

		await self.post_glance(
			"status", shard=shard_id, state=state
		)

	@commands.Cog.listener()
	async def on_resumed(self, shard_id):
		state = ShardState.ONLINE
		self.set_state(shard_id, state)

		await self.post_glance(
			"status", shard=shard_id, state=state
		)

	# Only works if fetch_offline_members
	@commands.Cog.listener()
	async def on_shard_ready(self, shard_id):
		state = ShardState.ONLINE
		self.set_state(shard_id, state)

		await self.post_glance(
			"status", shard=shard_id, state=state
		)


	async def handle_metrics(self, req):
		"""aiohttp handler for Prometheus metrics."""
		registry = REGISTRY

		if 'name[]' in req.query:
			registry = registry.restricted_registry(req.query['name[]'])

		output = prometheus_client.generate_latest(registry)
		return web.Response(
			body=output,
			headers=self._headers
		)


setup = Metrics.setup
