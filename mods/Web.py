import asyncio
import logging

from aiohttp import web
from mods.cog import Cog

logging.getLogger("aiohttp.access").setLevel(logging.WARN)

class Web(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.loop = bot.loop
		self.app = web.Application(loop=self.loop)
		self.handlers = {}
		self._ready = asyncio.Event(loop=self.loop)

		self.add_handler('GET', '/', self.default_handler)


		metrics = bot.get_cog('Metrics').handle_metrics
		self.add_handler('GET', '/metrics', metrics)

		self.loop.create_task(self.start_app())

	def cog_unload(self):
		self.loop.create_task(self.stop_app())

	@staticmethod
	async def default_handler(request):
		return web.Response(status=403)

	def add_handler(self, method, location, handler):
		self.handlers[method, location] = handler

		if self._ready.is_set():
			self.loop.create_task(self.reload())

	async def reload(self):
		await self.stop_app()
		self.app = web.Application(loop=self.loop)
		await self.start_app()

	async def start_app(self):
		for (method, location), handler in self.handlers.items():
			self.app.router.add_route(method, location, handler)

		self.app.freeze()
		await self.app.startup()

		self.handler = self.app.make_handler()
		self.server = await self.loop.create_server(
			self.handler, '0.0.0.0', 8000
		)
		self._ready.set()

	async def stop_app(self):
		await self._ready.wait()
		self.server.close()
		await self.server.wait_closed()
		await self.app.shutdown()
		await self.handler.shutdown(10)
		await self.app.cleanup()
		self._ready.clear()

setup = Web.setup
