import asyncio
import inspect
import textwrap
import time
import traceback
from contextlib import redirect_stdout
from copy import copy
from io import StringIO

import discord
from discord.ext import commands

import objgraph
from mods.cog import Cog
from utils import checks
from utils.funcs import get_prefix


class Debug(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.sessions = set()
		self.last_result = None
		self.format_code = bot.funcs.format_code
		self.cleanup_code = bot.funcs.cleanup_code
		self.code_api = bot.funcs.code_api
		self.rex_map = bot.funcs.rex_map
		self.f_api = bot.funcs.f_api
		self.hastebin = bot.funcs.hastebin

		if bot.dev_mode:
			self.enable_debug()


	@staticmethod
	def enable_debug(wait=False):
		import ptvsd
		ptvsd.enable_attach(("0.0.0.0", 5678))
		if wait:
			ptvsd.wait_for_attach()


	@commands.command()
	@commands.is_owner()
	async def load(self, ctx, *, module:str):
		mod = f"mods.{module}"
		msg = await ctx.send(f"ok, loading `{mod}`")
		try:
			ctx.bot.load_extension(mod)
		except ImportError:
			await msg.edit(content='\N{WARNING SIGN} Module does not exist.')
		except Exception as e:
			await msg.edit(content=self.format_code(e))
		else:
			await msg.edit(content=f"ok, loaded `{mod}`")

	@commands.command()
	@commands.is_owner()
	async def unload(self, ctx, *, module:str):
		mod = f"mods.{module}"
		msg = await ctx.send(f"ok, unloading `{mod}`")
		try:
			ctx.bot.unload_extension(mod)
		except ImportError:
			await msg.edit(content='\N{WARNING SIGN} Module does not exist.')
		except Exception as e:
			await msg.edit(content=self.format_code(e))
		else:
			await msg.edit(content=f"ok, unloaded `{mod}`")

	async def reload_funcs(self):
		funcs = copy(self.bot.funcs)
		self.bot.unload_extension('utils.funcs')
		try:
			self.bot.load_extension('utils.funcs')
		except Exception as e:
			self.bot.funcs = funcs
			return str(e)

	@commands.group(invoke_without_command=True)
	@commands.is_owner()
	async def reload(self, ctx, *, module:str):
		if module.lower() == 'funcs':
			result = await asyncio.wait_for(self.reload_funcs(), 5, loop=self.bot.loop)
			if not isinstance(result, str):
				await ctx.send('\N{WHITE HEAVY CHECK MARK} Reloaded bot functions.')
			else:
				await ctx.send(self.format_code(result))
		else:
			mod = f'mods.{module}'
			msg = await ctx.send(f"ok, reloading `{mod}`")
			try:
				self.bot.reload_extension(mod)
			except:
				await msg.edit(content=self.format_code(traceback.format_exc()))
			else:
				await msg.edit(content=f"ok, reloaded `{module}`")

	@commands.command()
	@commands.is_owner()
	async def update(self, ctx):
		t = time.time()
		await self.bot.funcs.git_update()
		await ctx.send('ok, pulled from git in `{:.01f}s`'.format(time.time() - t))

	@commands.command()
	@commands.is_owner()
	async def die(self, ctx):
		await ctx.send("Drinking bleach.....")
		await self.bot.logout()

	@commands.command()
	@commands.is_owner()
	async def loop(self, ctx, times:int, *, command):
		"""Loop a command a x times."""
		msg = copy(ctx.message)
		msg.content = command
		ctx = await self.bot.get_context(msg, None)
		for i in range(times):
			if i == 0:
				await self.bot.invoke(ctx)
			else:
				await ctx.reinvoke()

	def get_syntax_error(self, e):
		return '```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```'.format(e, '^', type(e).__name__)

	@commands.command()
	@commands.is_owner()
	async def repl(self, ctx):
		"""Launches an interactive REPL session."""
		variables = {
			'ctx': ctx,
			'bot': self.bot,
			'message': ctx.message,
			'server': ctx.guild,
			'guild': ctx.guild,
			'channel': ctx.channel,
			'author': ctx.author,
			'commands': commands,
			'_': None
		}
		variables.update(globals())
		if ctx.channel.id in self.sessions:
			return await ctx.send('Already running a REPL session in this channel. Exit it with `quit`.')
		self.sessions.add(ctx.channel.id)
		await ctx.send('Enter code to execute or evaluate. `exit()` or `quit` to exit.')
		def check(m):
			return m.author.id == ctx.author.id and \
						 m.channel.id == ctx.channel.id and \
						 m.content.startswith('`')
		while True:
			try:
				response = await self.bot.wait_for('message', check=check, timeout=10.0 * 60.0)
			except asyncio.TimeoutError:
				await ctx.send('Exiting REPL session.')
				self.sessions.remove(ctx.channel.id)
				break
			cleaned, haste = await self.cleanup_code(response.content, True)
			if cleaned in ('quit', 'exit', 'exit()'):
				await ctx.send('Exiting.')
				return self.sessions.remove(ctx.channel.id)
			executor = exec
			if cleaned.count('\n') == 0:
				try:
					code = compile(cleaned, '<repl session>', 'eval')
				except SyntaxError:
					pass
				else:
					executor = eval
			if executor is exec:
				try:
					code = compile(cleaned, '<repl session>', 'exec')
				except SyntaxError as e:
					await ctx.send(self.get_syntax_error(e))
					continue
			variables['message'] = response
			fmt = None
			stdout = StringIO()
			try:
				with redirect_stdout(stdout):
					result = executor(code, variables)
					if inspect.isawaitable(result):
						result = await result
			except Exception as e:
				value = stdout.getvalue()
				fmt = f'```py\n{value}{traceback.format_exc()}\n```'
			else:
				value = stdout.getvalue()
				if result is not None:
					fmt = self.format_code(f"{value}{result}", truncate=False)
					variables['_'] = result
				elif value:
					fmt = self.format_code(value, truncate=False)
			try:
				if fmt:
					if haste:
						fmt = await self.hastebin(fmt)
					elif len(fmt) >= 2000:
						fmt = fmt[:1992] + "[...]```"
					await ctx.send(fmt)
			except discord.Forbidden:
				pass
			except discord.HTTPException as e:
				await ctx.send(f'Unexpected error: `{e}`')

	@commands.command()
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def debug(self, ctx, *, code:str):
		result = await self.code_api('24', code, fmt=True)
		await ctx.send(result[0] if result[0] else result[1], replace_mentions=True)

	@commands.group(aliases=['runcode', 'rextester'], invoke_without_command=True)
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def rex(self, ctx, lang:str, *, code:str):
		if lang.startswith('```') and code.endswith('```'):
			code = lang+'\n'+code
			lang = code.split('\n')[0][3:].lower()
		result = await self.code_api(lang.lower(), code, fmt=True)
		await ctx.send(result[0] if result[0] else result[1], replace_mentions=True)

	@rex.command(name='list', aliases=['languages'])
	@commands.cooldown(1, 15, commands.BucketType.guild)
	async def rex_list(self, ctx):
		m = self.rex_map
		msg = "Use key or name for language input\n" + \
					'\n'.join([f"`{x}`: {', '.join(m[x])}" for x in m])
		await ctx.send(await self.hastebin(msg))

	@commands.command(name='eval')
	@commands.is_owner()
	async def _eval(self, ctx, *, code:str):
		env = {
			'bot': self.bot,
			'ctx': ctx,
			'channel': ctx.channel,
			'author': ctx.author,
			'guild': ctx.guild,
			'server': ctx.guild,
			'message': ctx.message,
			'_': self.last_result
		}
		env.update(globals())
		body, haste = await self.cleanup_code(code, True)
		stdout = StringIO()
		to_compile = 'async def func():\n{0}'.format(textwrap.indent(body, '  '))
		try:
			exec(to_compile, env)
		except SyntaxError as e:
			return await ctx.send(self.get_syntax_error(e))
		func = env['func']
		try:
			with redirect_stdout(stdout):
				ret = await func()
		except Exception as e:
			value = stdout.getvalue()
			await ctx.send(self.format_code(f'{value}{traceback.format_exc()}'))
		else:
			value = stdout.getvalue()
			try:
				await ctx.message.add_reaction('\u2705')
			except:
				pass
			if ret is None:
				fmt = value
			else:
				self.last_result = ret
				fmt = f'{value}{ret}'
			if fmt:
				if haste:
					fmt = await self.hastebin(fmt)
				else:
					fmt = self.format_code(fmt)
				await ctx.send(fmt)

	@commands.command()
	@commands.is_owner()
	async def runas(self, ctx, user:discord.User, cmd:str, *, args:str=None):
		try:
			msg = ctx.message
			msg.author = user
			prefix = await get_prefix(self.bot, msg)
			msg.content = f"{prefix[0][0]}{cmd}{' ' + args if args else ''}"
			await self.bot.on_message(msg)
		except Exception as e:
			await ctx.send(self.format_code(e))

	@commands.command()
	@commands.is_owner()
	async def sql(self, ctx, *, sql:str):
		"""Debug SQL"""
		try:
			q = await self.cursor.execute(sql)
			if hasattr(q, 'fetchall'):
				result = await q.fetchall()
				await ctx.send("**SQL RESULTS**\n"+str(result))
			else:
				await ctx.send('\N{WHITE HEAVY CHECK MARK} `SQL Executed.`')
		except Exception as e:
			await ctx.send(self.format_code(e))
			raise

	@commands.command()
	@commands.is_owner()
	async def sql2(self, ctx, *, sql:str):
		"""Debug SQL"""
		try:
			q = await self.bot.mysql._execute(sql, args=None, fetch=True)
			await ctx.send("**SQL RESULTS**\n"+str(await q.fetchall()))
		except Exception as e:
			await ctx.send(self.format_code(e))
			raise

	@commands.command(name="objgraph")
	@commands.is_owner()
	async def objgraph_(self, ctx):
		out = await self.bot.loop.run_in_executor(None, objgraph.most_common_types)
		await ctx.send(str(out))

	@commands.command()
	@commands.is_owner()
	async def objgrowth(self, ctx):
		stdout = StringIO()
		with redirect_stdout(stdout):
			await self.bot.loop.run_in_executor(None, objgraph.show_growth)
		await ctx.send(stdout.getvalue())

	@commands.command(aliases=['feval'])
	@checks.owner_or_ids(687945863053443190)
	async def fapieval(self, ctx, *, code:str):
		code = await self.cleanup_code(code)
		r = await self.f_api('eval', text=code, raw=True)
		await ctx.send(self.format_code(r, 'js'))

def setup(bot):
	bot.add_cog(Debug(bot))
