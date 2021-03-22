import asyncio
import inspect
import math
import os
import re
import sys
import traceback
import uuid
from base64 import b64decode
from collections import OrderedDict, deque
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from itertools import chain

import aiohttp
from async_timeout import timeout as Timeout

import discord
from discord.backoff import ExponentialBackoff
from discord.ext import commands
from discord.utils import get as dget

import sentry_sdk
import ujson as json
from yarl import URL
from utils import cache
from utils.converters import setup_converters
from utils.cooldown import *


class Object(object):
	pass


@cache.cache(maxsize=1024)
async def query_prefix(bot, arg, channel=False):
	if channel:
		q = await bot.mysql.cursor.execute(f"SELECT prefix,channel FROM `prefix_channel` WHERE channel={arg}")
		result = await q.fetchone()
	else:
		q = await bot.mysql.cursor.execute(f"SELECT prefix,d FROM `prefix` WHERE guild={arg}")
		result = await q.fetchall()
	return result

async def get_prefix(bot, message):
	if bot.dev_mode:
		prefix = ','
	elif bot.self_bot:
		prefix = 'self.'
	else:
		prefix = '.'
	prefixes = [prefix]
	if not bot.self_bot and message.guild and not message.content.startswith(f"{prefix}prefix"):
		prefix_set = False
		result = await query_prefix(bot, message.channel.id, channel=True)
		if result:
			if result['channel'] == message.channel.id:
				prefixes.append(result['prefix'].lower())
				prefix_set = True
		if not prefix_set:
			result = await query_prefix(bot, message.guild.id)
			for x in result:
				if x['d'] and not prefix_set:
					prefix_set = True
				prefixes.append(x['prefix'].lower())
		if prefix_set:
			del prefixes[0]
	if message.guild is None and not bot.self_bot:
		prefixes.append('')
	prefixes.extend(commands.bot.when_mentioned(bot, message))
	return prefixes

async def get_user_info(state, user_id):
	users = list(state._users.values())
	user = dget(users, id=user_id)
	if not user:
		try:
			data = await state.http.get_user(user_id)
		except discord.NotFound:
			return None
		user = discord.User(state=state, data=data)
	return user

async def replace_mentions(state, guild, content:str, limit:int=None):
	match = re.findall(r"(<@!?(\d+)>)", content)
	if match:
		if limit:
			match = match[limit:]
		for mention, i in match:
			user = await get_user_info(state, int(i))
			if user is not None:
				content = content.replace(mention, f'@{user}')
	if guild:
		match = re.findall(r"(<@&(\d+)>)", content)
		if match:
			for mention, i in match:
				role = dget(guild.roles, id=int(i))
				if role:
					content = content.replace(mention, f'@{role}')
	return content

class LimitedDict(OrderedDict):
	def __init__(self, *args, **kwargs):
		self.maxlen = kwargs.pop('maxlen', None)
		super().__init__(self, *args, **kwargs)
		self._check_size()

	def __setitem__(self, key, value):
		super().__setitem__(key, value)
		self._check_size()

	def _check_size(self):
		if self.maxlen != None:
			while len(self) > self.maxlen:
				self.popitem(last=False)

async def reaction_backoff(partial):
	b = None
	for _ in range(5):
		try:
			await partial()
		except discord.HTTPException:
			if b is None:
				b = ExponentialBackoff(base=2.0)
			await asyncio.sleep(b.delay())
			continue
		except (discord.Forbidden, discord.NotFound):
			break
		else:
			return True


#save some ram

class NameOnlyActivity:
	__slots__ = ('name',)

	def __init__(self, data):
		self.name = data.get('name', None)

def create_activity(data):
	if data:
		return NameOnlyActivity(data)


class FakeMessage:
	def __init__(self, ctx, mid):
		self._state = ctx._state

		self.id = mid

		self.channel = Object()
		self.channel.id = ctx.channel.id

		# NO REFS TO MESSAGE/GUILD
		del ctx

	async def delete(self):
		return await discord.Message.delete(self)


class LimitError(Exception): pass

class Funcs(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.loop = bot.loop
		self._release = None
		self.init_aliases()
		self.image_mimes = (
			'image/png',
			'image/jpeg',
			'image/jpg',
			'image/webp',
			'image/bmp',
			'image/pjpeg',
			'image/x-icon',
			'image/x-ms-bmp'
		)
		self.image_extensions = [f".{x[6:]}" for x in self.image_mimes[:5]]
		self.extension_checks = (
			lambda url: any(URL(url).path.endswith(x) for x in self.image_extensions),
			lambda url: URL(url).path.endswith('.gif')
		)
		self.colors = (
			'red',
			'blue',
			'green',
			'gold',
			'dark_blue',
			'dark_gold',
			'dark_green',
			'dark_grey',
			'dark_magenta',
			'dark_orange',
			'dark_purple',
			'dark_red',
			'dark_teal',
			'darker_grey',
			'default',
			'light_grey',
			'lighter_grey',
			'magenta',
			'orange',
			'purple',
			'teal'
		)
		self.color_count = 0
		self.emote_regex = re.compile(r"<(a)?:[a-zA-Z0-9\_]+:([0-9]+)>")
		self.mention_regex = re.compile(r"<@!?([0-9]+)>")
		self.switches = {}
		self.keys = {}
		self.code_block = '```{0}\n{1}\n```'
		self.rex_map = {
			'39': ['ada'],
			'15': ['assembly', 'asm'],
			'38': ['bash'],
			'44': ['brainfuck', 'bf'],
			'1': ['c#'],
			'7': ['c++(gcc)', 'c++', 'cpp'],
			'27': ['c++(clang)'],
			'28': ['c++(vc++)'],
			'6': ['c(gcc)', 'c'],
			'26': ['c(clang)'],
			'29': ['c(vc)'],
			'18': ['commonlisp', 'lisp'],
			'30': ['d'],
			'41': ['elixir', 'ex'],
			'40': ['erlang'],
			'3': ['f#'],
			'45': ['fortran', 'fort'],
			'20': ['go'],
			'11': ['haskell', 'hs'],
			'4': ['java'],
			'17': ['javascript', 'js'],
			'43': ['kotlin', 'kot'],
			'14': ['lua'],
			'33': ['mysql'],
			'23': ['node.js', 'node'],
			'42': ['ocaml'],
			'25': ['octave'],
			'10': ['objective-c', 'oc'],
			'35': ['oracle'],
			'9': ['pascal'],
			'13': ['perl'],
			'8': ['php', 'php7'],
			'34': ['postgresql', 'psql', 'postgres'],
			'19': ['prolog'],
			'5': ['python2', 'python2.7', 'py2.7', 'py2'],
			'24': ['python', 'python3', 'py', 'py3'],
			'31': ['r'],
			'12': ['ruby', 'rb'],
			'21': ['scala'],
			'22': ['scheme'],
			'16': ['sqlserver'],
			'37': ['swift'],
			'32': ['tcl'],
			'2': ['visualbasic', 'vb']
		}
		self.rex_compiler_map = {
			'7': '-Wall -std=c++14 -O2 -o a.out source_file.cpp',
			'27': '-Wall -std=c++14 -stdlib=libc++ -O2 -o a.out source_file.cpp',
			'28': r'source_file.cpp -o a.exe /EHsc /MD /I C:\boost_1_60_0 /link /LIBPATH:C:\boost_1_60_0\stage\lib',
			'6': '-Wall -std=gnu99 -O2 -o a.out source_file.c',
			'26': '-Wall -std=gnu99 -O2 -o a.out source_file.c',
			'29': 'source_file.c -o a.exe',
			'30': 'source_file.d -ofa.out',
			'20': '-o a.out source_file.go',
			'11': '-o a.out source_file.hs'
		}
		self.offload_ip = "http://192.168.15.17"
		self.buckets = (
			CooldownMapping(Cooldown(1, 5)),
			CooldownMapping(Cooldown(1, 7))
		)
		self.default_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36'}
		self.session = None
		self._create_session()
		self.proxies = open(self.discord_path('utils/proxies.txt')).read().split('\n')
		self.proxy = "http://proxy.wrmsr.io:3128"
		self.imis_host = "http://imis.mods.nyc/objects"
		self.fapi_host = "https://fapi.wrmsr.io"

		# Sentry
		self.dsn = "https://b4e47d43cb704468a3df7856d7da9fc8@sentry.io/1218283"

		# Auto pull from git on bot start
		self.loop.create_task(self.git_update())
		# Get the current commit hash for Sentry
		self.loop.create_task(self.update_release(True))

	def init_aliases(self):
		self.cursor = self.bot.mysql.cursor
		self.replace_mentions = replace_mentions
		#Globals
		bot = self.bot
		bot.funcs = self
		bot.pruned_messages = deque(maxlen=85000)
		#Utils
		bot.escape = bot.mysql.escape
		bot.get_images = self.get_images
		bot.run_process = self.run_process
		bot.get_json = self.get_json
		bot.bytes_download = self.bytes_download
		bot.command_help = self.command_help
		bot.random = self.random
		bot.get_text = self.get_text
		bot.post_data = self.post_data
		bot.get_user = self.get_user
		bot.get_member = self.get_member
		#Paths
		bot.path = Object()
		bot.path.discord = self.discord_path
		bot.path.files = self.files_path
		#converters
		setup_converters()
		#ignore events
		rn = lambda _: None
		bot._connection.parse_typing_start = rn
		bot._connection.parse_channel_pins_update = rn

		bot._connection._cache_members = False

	def cog_unload(self):
		self._close_session()

	def _create_session(self):
		self.session = aiohttp.ClientSession(headers=self.default_headers, loop=self.loop)

	def _close_session(self):
		if self.session:
			asyncio.ensure_future(self.session.close())

	def discord_path(self, path):
		return os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), path)

	def files_path(self, path):
		return self.discord_path('files/'+path)

	@cache.cache(maxsize=1024)
	async def is_off(self, guild, member):
		sql = f"SELECT user FROM `muted` WHERE guild={guild} AND user={member}"
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		return result and result['user'] == member

	# TTL Cache 5 mins
	@cache.cache(maxsize=300, strategy=cache.Strategy.timed)
	async def query_blacklist(self, table, *args, single=True):
		# Global
		if table == 1:
			sql = 'SELECT user FROM `global_blacklist` WHERE user=%s'
		# Except
		elif table == 2:
			sql = "SELECT role FROM `except_blacklist` WHERE guild=%s"
		# Server
		elif table == 3:
			sql = "SELECT user FROM `blacklist` WHERE guild=%s AND user=%s"
		# Channel
		elif table == 4:
			sql = "SELECT channel FROM `channel_blacklist` WHERE channel=%s"

		q = await self.cursor.execute(sql % args)
		if single:
			return await q.fetchone()
		return await q.fetchall()

	async def is_blacklisted(self, message):
		guild = message.guild
		if guild and guild.me:
			perms = message.channel.permissions_for(guild.me)
			# no perms why bother
			if not perms.send_messages or not perms.read_messages:
				return True

		author = message.author
		if await self.bot.is_owner(author) or (guild and guild.owner_id == author.id):
			return False

		q = await self.query_blacklist(1, author.id)
		if q:
			return True
		if guild is None:
			return False

		if await self.is_off(guild.id, author.id):
			return True

		if isinstance(author, discord.Member):
			result = await self.query_blacklist(2, guild.id, single=False)
			if result:
				roles = [dget(guild.roles, id=x['role']) for x in result]
				for i, role in enumerate(roles):
					if role is None:
						await self.cursor.execute(
							f"DELETE FROM `except_blacklist` WHERE guild={guild.id} AND role={result[i]['role']}"
						)
				return not any(x in roles for x in author.roles)

		q = await self.query_blacklist(3, guild.id, author.id)
		if q:
			return True

		q = await self.query_blacklist(4, message.channel.id)
		if q:
			return 'blacklist' not in message.content

		return False

	# 0 - global
	# 1 - server
	# 2 - channel
	# 3 - user
	# 4 - role
	async def command_check(self, message, command):
		if await self.bot.is_owner(message.author):
			return False
		sql = 'SELECT * FROM `command_blacklist` WHERE type=0 AND command=%s'
		q = await self.cursor.execute(sql, (command,))
		result = await q.fetchone()
		if result:
			return True
		elif message.guild is None:
			return False
		elif message.guild.owner_id == message.author.id:
			return False
		topic_match = None
		if message.channel.topic:
			command_escape = re.escape(command)
			topic_regex = re.compile(r"((\[|\{)(\+|\-)?"+command_escape+r"(\]|\}))", re.I|re.S)
			match = topic_regex.findall(message.channel.topic.lower())
			if match:
				if match[0][2] == '+' or not match[0][2]:
					topic_match = False
				elif match[0][2] == '-':
					topic_match = True
		if topic_match:
			return True
		q = await self.cursor.execute(f'SELECT * FROM `command_blacklist` WHERE guild={message.guild.id}')
		result = await q.fetchall()
		for s in result:
			if s['command'] != command:
				continue
			if s['type'] == 1:
				if topic_match is False:
					return False
				return True
			elif s['type'] == 2:
				if s['channel'] == message.channel.id:
					return True
			elif s['type'] == 3:
				if s['user'] == message.author.id:
					return True
			elif s['type'] == 4:
				for role in message.author.roles:
					if s['role'] == role.id:
						return True
		return False

	async def get_mime(self, url):
		async with Timeout(10):
			async with self.session.head(url, proxy=self.proxy, allow_redirects=True) as r:
				r.raise_for_status()
				return r.headers.get('Content-Type', '').lower().split(';')[0]

	async def isimage(self, url:str):
		try:
			mime = await self.get_mime(url)
			return mime in self.image_mimes
		except:
			return False

	async def isgif(self, url:str):
		try:
			mime = await self.get_mime(url)
			return mime == "image/gif"
		except:
			return False

	# Use to keep timeout exceptions
	async def _bytes_download(self, url:str, timeout:int=10, headers=None, **kwargs):
		p = kwargs.pop('proxy', None)
		if p:
			p = self.proxy

		limit = kwargs.pop('limit', None)
		async with Timeout(timeout):
			async with self.session.get(url, headers=headers, proxy=p, **kwargs) as r:
				r.raise_for_status()
				if limit:
					cl = int(r.headers.get('content-length', 0))
					if cl > limit:
						raise LimitError(f"Content exceeds size limit (> {cl} B)")
					chunk = await r.content.readexactly(cl)
					if not chunk:
						return False
					b = BytesIO(chunk)
				else:
					b = BytesIO(await r.read())
				b.seek(0)
				return b

	# Return false on all errors, including timeouts..
	async def bytes_download(self, *args, **kwargs):
		try:
			return await self._bytes_download(*args, **kwargs)
		except:
			return False

	async def get_json(self, url:str, timeout:int=5, headers=None, data=None, content_type='application/json'):
		method = self.session.post if data else self.session.get
		try:
			async with Timeout(timeout):
				async with method(url, headers=headers, data=data) as r:
					r.raise_for_status()
					load = await r.json(content_type=content_type)
					return load
		except:
			return {}

	async def get_text(self, url:str, **kwargs):
		p = kwargs.pop('proxy', None)
		if p:
			p = self.proxy
		dlimit = kwargs.pop("discord_limit", False)
		try:
			async with Timeout(kwargs.pop('timeout', 5)):
				async with self.session.get(url, proxy=p, **kwargs) as r:
					if dlimit:
						# Max 6 bytes per character (emojis)
						# 2000 discord char limit
						chunk = await r.content.read(6 * 2000)
						if not chunk:
							return False
						return chunk.decode("utf-8")

					return await r.text()
		except:
			return False

	async def get_cookies(self, url:str, **kwargs):
		try:
			async with Timeout(kwargs.pop('timeout', 5)):
				async with self.session.get(url, **kwargs) as r:
					return r.cookies
		except:
			return False

	async def post_data(self, url:str, data=None, **kwargs):
		t = kwargs.pop('timeout', 5)
		headers = kwargs.pop('headers', self.default_headers)
		try:
			async with Timeout(t):
				async with self.session.post(url, headers=headers, data=data) as resp:
					r = True
					if kwargs.pop('read', False):
						r = await resp.read(), resp.status
					elif kwargs.pop('json', False):
						r = await resp.json()
					elif kwargs.pop('text', False):
						r = await resp.text(encoding='utf-8')
					return (r, resp.headers) if kwargs.get('rheaders') else r
		except Exception as e:
			if self.bot.dev_mode:
				print(e)
				raise e
			return False

	def get_proxy(self):
		return self.get_key('proxies', self.proxies)

	async def proxy_request(self, method:str, url:str, **kwargs):
		json = kwargs.pop('json', False)
		text = kwargs.pop('text', False)
		b = kwargs.pop('b', False)
		rheaders = kwargs.pop('rheaders', False)
		#try 2 times incase bad proxy
		retries = kwargs.pop('max_retries', 2)
		for i in range(retries):
			try:
				async with Timeout(kwargs.pop('timeout', 10)):
					ba = aiohttp.Basic
					('user2016958', 'GDJCFP23')
					proxy = f"http://{self.get_proxy()}:6060"
					async with getattr(self.session, method)(url, proxy=proxy, proxy_auth=ba, **kwargs) as resp:
						# assert resp.status == 200
						if json:
							r = await resp.json(content_type=None)
						elif text:
							r = await resp.text()
						elif b:
							r = BytesIO(await resp.read())
							r.seek(0)
						else:
							r = resp
						return (r, resp.headers) if rheaders else r
			except Exception as e:
				if self.bot.dev_mode:
					print(e)
					raise e
				elif i < (retries - 1):
					continue
				return False

	async def generic_api(self, api:str, url:str=None, **kwargs):
		_json = kwargs.pop('json', False)
		#text kwarg taken
		raw = kwargs.pop('raw', False)
		if url:
			kwargs['url'] = url
		data = kwargs.pop('body', None) or kwargs
		headers = {
			'Authorization': "bd543992-17cd-435f-b463-fec1b894ad26"
		}
		data = await self.post_data(f"{self.offload_ip}:8765/{api}", data,
																headers=headers, read=not _json and not raw,
																text=raw, json=_json, timeout=120)
		if not data:
			return False
		elif _json or raw:
			return data
		code = data[1]
		if code == 500 or code == 503:
			return data[0].decode('utf-8')
		b = BytesIO(data[0])
		b.seek(0)
		return b

	async def f_api(self, api:str, *urls:str, **kwargs):
		raw = kwargs.pop('raw', False)
		_json = kwargs.pop('json', False)
		payload = {'args': {**kwargs}}
		if urls:
			payload['images'] = list(urls)
		headers = {
			'Content-Type': 'application/json',
			'User-Agent': 'NotSoBot (superior bot)',
			'Authorization': "Bearer 4e3a26d97e64093299c3afffa3d54"
		}
		payload = json.dumps(payload, ensure_ascii=False)
		data = await self.post_data(f'{self.fapi_host}/{api}', payload, headers=headers,
																read=not raw and not _json, text=raw, json=_json, timeout=60)
		assert data, 'API is down or took too long.'
		if _json or raw:
			return data
		code = data[1]
		if code != 200:
			return data[0].decode()
		b = BytesIO(data[0])
		b.seek(0)
		return b

	async def run_process(self, args, response=False, b=False, stdin=None, shell=False):
		func = asyncio.create_subprocess_exec
		if shell:
			func = asyncio.create_subprocess_shell
			args = (' '.join(args),)
		inp = stdin.read() if isinstance(stdin, BytesIO) else stdin
		stdin = stdin or asyncio.subprocess.PIPE
		try:
			async with Timeout(120):
				proc = await func(
					*args, stdin=stdin, stderr=asyncio.subprocess.PIPE,
					stdout=asyncio.subprocess.PIPE, loop=self.loop
				)
				data, _ = await proc.communicate(input=inp)
		except asyncio.TimeoutError:
			proc.terminate()
			# let it cleanup
			await asyncio.sleep(5)
			if not proc.returncode: # force kill if taking too long
				proc.kill()
			assert False, 'Processing timeout exceeded.'
		if b:
			b = BytesIO(data)
			return b.read()
		elif response:
			try:
				decoded = data.decode('ascii')
			except:
				decoded = data.decode('utf-8')
			return decoded.rstrip()
		return True

	async def truncate(self, channel, content, *args, embeds=None, **kwargs):
		if not embeds and not content:
			return
		split = [[content[i:i + 1999]] for i in range(0, len(content), 1999)]
		if embeds:
			l = len(split)
			for i, e in enumerate(embeds):
				if i <= l - 1:
					split[i].append(e)
				else:
					split.append((None, e))
		files = kwargs.pop('files', None)
		for i, c in enumerate(split):
			if files:
				if i > 0:
					files = None
				else:
					kwargs['files'] = files
			await channel.send(c[0], *args, embed=c[1] if len(c) > 1 else None, **kwargs)

	# accept Attachment or Embed
	def image_check(self, i, ret=False, check=0):
		if isinstance(i, discord.embeds.Embed):
			i = i.image or i.thumbnail
		if i:
			if (check is not None and not i.width) or (i.width and (i.width > 5000 or i.height > 5000)):
				return False
			url = i.url
			host = URL(url).host
			# yarl has a parser bug with discord proxy cache args
			if not re.match(r"^(.*\.)?discordapp\.(net|com)", host, re.I):
				url = i.proxy_url
			if check is not None:
				check = self.extension_checks[check]
				if not check(url.lower()):
					return False
			return url if ret else True
		return False

	# check 0 = image, 1 = gif
	async def get_attachment_image(self, ctx, check=0):
		async for m in ctx.channel.history(before=ctx.message, limit=25):
			for i in chain(m.attachments, m.embeds):
				la = self.image_check(i, True, check)
				if la:
					return la

	async def get_images(self, ctx, **kwargs):
		message = ctx.message
		mentions = [dget(message.mentions, id=int(x)) for x in \
								self.mention_regex.findall(message.content)]
		limit = kwargs.pop('limit', 8)
		urls = kwargs.pop('urls', [])
		gif = kwargs.pop('gif', False)
		msg = kwargs.pop('msg', True)
		img_urls = []

		if gif:
			check_func = self.isgif
		else:
			check_func = self.isimage
		if urls is None:
			urls = []
		elif isinstance(urls, str):
			urls = [urls]
		else:
			urls = list(urls)

		scale = kwargs.pop('scale', None)
		scale_msg = None
		int_scale = None

		if scale:
			float_scale = kwargs.pop('float', False)
			neg_scale = kwargs.pop('negative', False)
			scale_limit = scale
			limit += 1
	
		if urls and len(urls) > limit:
			await ctx.send('\N{NO ENTRY} `Max image limit (<= {0})`'.format(limit))
			ctx.command.reset_cooldown(ctx)
			return False

		for user in mentions:
			if user:
				if not gif:
					img_urls.append(str(user.avatar_url_as(format='png')))
				elif user.is_avatar_animated():
					img_urls.append(str(user.avatar_url))

		icheck = int(gif)
		for i in message.attachments:
			if self.image_check(i, False, icheck):
				img_urls.append(i.proxy_url)

		a = False
		if gif:
			b = False

		for count, url in enumerate(urls, 1):
			user = None
			if url.startswith('<@'):
				continue
			ematch = self.emote_regex.match(url)
			if not ematch and url.startswith('<http'):
				url = url.strip('<').strip('>')
			if not url.startswith('http'):
				url = f'http://{url}'
			try:
				if scale:
					surl = url[8:] if url.startswith('https://') else url[7:]
					fl = float(surl)
					if kwargs.pop('make_negative', False):
						fl = fl * -1
					f = math.floor(fl)
					if str(abs(f) if neg_scale else f).isdigit():
						int_scale = fl if float_scale else f
						assert len(surl) < 15
						scale_msg = '`Scale: {0}`\n'.format(abs(int_scale) if neg_scale else int_scale)
						if abs(int_scale) > abs(scale_limit) and not await self.bot.is_owner(ctx.author):
							int_scale = scale_limit
							scale_msg = '`Scale: {0} (Limit: <= {1})`\n'.format(abs(int_scale) if neg_scale else int_scale, scale_limit)
						continue
			except:
				pass
			check = await check_func(url)
			if not check and not gif:
				check = await self.isgif(url)
				if check:
					if msg:
						await ctx.send("\N{WARNING SIGN} This command is for images, not gifs (use `gmagik` or `gascii`)!")
					ctx.command.reset_cooldown(ctx)
					return False
				elif not img_urls or a:
					name = url[8:] if url.startswith('https://') else url[7:]
					e = await self.emoji_path(name, point=True)
					if e:
						img_urls.append(f'http://bot.mods.nyc/twemoji/{e}.png')
						a = True
						continue
					else:
						if ematch and not ematch.group(1):
							img_urls.append(f'https://cdn.discordapp.com/emojis/{ematch.group(2)}.png')
							a = True
							continue
						else:
							member = await self.find_member(message, name, 2)
							if member:
								img_urls.append(str(member.avatar_url_as(format='png')))
								a = True
								continue
					if msg:
						await ctx.send('\N{WARNING SIGN} Unable to download or verify URL is valid.')
					ctx.command.reset_cooldown(ctx)
					return False
				else:
					if msg:
						await ctx.send('\N{WARNING SIGN} Image `{0}` is Invalid!'.format(count))
					continue
			elif gif and not check:
				check = await self.isimage(url)
				if check:
					if msg:
						await ctx.send("\N{WARNING SIGN} This command is for gifs, not images (use `magik`)!")
					ctx.command.reset_cooldown(ctx)
					return False
				elif not img_urls or b:
					if ematch and ematch.group(1):
						img_urls.append(f'https://cdn.discordapp.com/emojis/{ematch.group(2)}.gif')
						continue
					else:
						name = url[8:] if url.startswith('https://') else url[7:]
						member = await self.find_member(message, name, 2)
						if member and member.avatar and member.is_avatar_animated():
							img_urls.append(str(member.avatar_url))
							b = True
							continue
					if msg:
						await ctx.send('\N{WARNING SIGN} Unable to download or verify URL is valid.')
					ctx.command.reset_cooldown(ctx)
					return False
				else:
					if msg:
						await ctx.send('\N{WARNING SIGN} Gif `{0}` is Invalid!'.format(count))
					continue
			img_urls.append(url)

		if not img_urls:
			attachment_images = await self.get_attachment_image(ctx, icheck)
			if attachment_images:
				img_urls.append(attachment_images)
			else:
				if msg:
					await ctx.send("\N{NO ENTRY} Please input url(s){0}or attachment(s).".format(', mention(s) ' if not gif else ' '))
				ctx.command.reset_cooldown(ctx)
				return False

		img_urls = list(set(img_urls))
		if scale:
			return img_urls, int_scale, scale_msg
		return img_urls or False

	def get_key(self, name, keys):
		if name not in self.keys:
			self.keys[name] = 0
		count = self.keys[name]
		try:
			if count == len(keys):
				self.keys[name] = 0
				count = 0
			return keys[count]
		finally:
			self.keys[name] += 1

	async def cleanup_code(self, content, hastebin=False):
		"""Automatically removes code blocks from the code."""
		if content.startswith('```') and content.endswith('```'):
			clean = '\n'.join(content.split('\n')[1:-1])
		else:
			clean = content.strip('` \n')
		if clean.startswith('http'):
			clean = await self.get_text(clean)
		if hastebin:
			if ' -haste' in clean:
				clean = clean.replace(' -haste', '')
				haste = True
			else:
				haste = False
		return clean if not hastebin else (clean, haste)

	@staticmethod
	def get_syntax_error(e):
		return '```py\n{0.text}{1:>{0.offset}}\n{2}: {0}```'.format(e, '^', type(e).__name__)

	async def command_help(self, ctx):
		cmd = ctx.invoked_subcommand or ctx.command
		hf = self.bot.old_help_command

		await hf.prepare_help_command(ctx, cmd)
		hf.context = ctx

		try:
			hf.add_command_formatting(cmd)
			hf.paginator.close_page()

			for page in hf.paginator.pages:
				await ctx.send(page.replace("\n", "fix\n", 1))
		finally:
			hf.context = None


	@staticmethod
	async def get_last_25(message):
		members = set()
		count = 0
		messages = message._state._messages

		for m in reversed(messages):
			if count >= 25:
				break
			elif m.channel == message.channel:
				members.add(m.author)
				count += 1

		if count < 20:
			try:
				async for m in message.channel.history(before=message, limit=25):
					if len(members) >= 25:
						break

					members.add(m.author)

					for member in m.mentions:
						members.add(member)

					messages.append(m)
			except:
				pass

			# cache members
			# guild = message.guild
			# for member in members:
			# 	if guild.get_member(member.id) is None:
			# 		guild._add_member(member)

		return members

	async def find_member(self, message, name, steps=2):
		guild = message.guild
		state = message._state
		gc = guild is None
		if gc:
			me = message.channel.me
		member = None

		if not isinstance(name, str):
			name = str(name)

		mention = self.mention_regex.match(name)
		if mention:
			uid = int(mention.group(1))
			if gc:
				member = dget([message.channel.recipient, me], id=uid)
			else:
				member = dget(message.mentions, id=uid)

			return member or await get_user_info(state, uid)

		try:
			if member is None and not self.bot.self_bot and name.isdigit() and self.is_id(name):
				uid = int(name)
				if not gc:
					try:
						member = await guild.fetch_member(uid)
					except discord.NotFound:
						pass
				if member is None:
					member = await get_user_info(state, uid)
		except ValueError:
			pass

		if member is None:
			name = name.lower()

			if not gc:
				# give it a head start
				async def query_members():
					try:
						return await guild.query_members(
							name, limit=5, cache=True
						)
					# TimeoutError not instance of asyncio for Tasks...
					except: # handle timeouts if we dont reach the await below
						pass
				query = self.loop.create_task(query_members())

			last_25 = None
			checks = [lambda m: m.name.lower() == name or m.display_name.lower() == name or str(m).lower() == name,
								lambda m: m.name.lower().startswith(name) or m.display_name.lower().startswith(name) or m.id == name,
								lambda m: name in m.display_name.lower() or name in m.name.lower()]
			for i in range(steps if steps <= len(checks) else len(checks)):
				check = checks[i]
				if i == 2 or (gc and i == 1): # last step or DM & 2nd
					member = discord.utils.find(checks[1], self.bot.get_all_members())
				elif not gc: # not DM/Group Chat
					if last_25 is None:
						last_25 = await self.get_last_25(message)

					member = discord.utils.find(check, last_25)
					if member is None:
						# check cache first for previous query
						member = discord.utils.find(check, guild.members)
						if member is None:
							# query is basically discords version of startswith
							if not gc and i >= 1:
								# lets fetch members & populate member cache with any hits
								await query
		
							member = discord.utils.find(check, guild.members)
				else:
					member = discord.utils.find(check, [message.author, me])

				if member is not None:
					break

		return member

	def random(self, image=False, ext:str=None):
		h = str(uuid.uuid4().hex)
		if image:
			return f"{h}.{ext or '.png'}"
		return h

	def get_color(self):
		if self.color_count >= len(self.colors):
			self.color_count = 0
		color = self.colors[self.color_count]
		self.color_count += 1
		return getattr(discord.Color, color)

	# kwargs: path=None, fmt=None, point=False, verify=False
	async def emoji_path(self, e, **kwargs):
		load = await self.generic_api(
			"is_emoji", json=True,
			e=e, **kwargs
		)
		return load['result'] if load else load

	async def png_svg(self, paths, size):
		load = await self.generic_api("svg_emoji",
			paths=paths, size=size,
			json=True
		)

		if load:
			return [BytesIO(b64decode(x)) for x in load['images']]
		return []


	#http://stackoverflow.com/a/34084933
	def get_deep_text(self, element):
		try:
			text = element.text or ''
			for subelement in element:
				text += self.get_deep_text(subelement)
			text += element.tail or ''
			return text
		except:
			return ''

	def format_code(self, txt:str, lang:str='py', truncate=True):
		if lang is None:
			lang = ''
		if not isinstance(txt, str):
			txt = str(txt)
		if truncate and len(txt) >= 2000:
			txt = txt[9:1996]
		return self.code_block.format(lang, txt)

	async def repl(self, code):
		variables = {
				'bot': self.bot,
				'last': None,
				'commands': commands,
				'discord': discord,
				'asyncio': asyncio,
				'cursor': self.cursor
		}
		cleaned = await self.cleanup_code(code)
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
				return self.get_syntax_error(e)
		fmt = None
		stdout = StringIO()
		try:
			with redirect_stdout(stdout):
				result = executor(code, variables)
				if inspect.isawaitable(result):
					result = await result
		except Exception as e:
			value = stdout.getvalue()
			fmt = f'{value}{traceback.format_exc()}'
		else:
			value = stdout.getvalue()
			if result is not None:
				fmt = f'{value}{result}'
				variables['last'] = result
			elif value:
				fmt = value
		return fmt

	#DISABLE CODE REVIEWING AT THIS POINT
	def get_lang(self, lang):
		m = self.rex_map
		key = None
		if lang.isdigit() and lang in m.keys():
			key = lang
		else:
			langs = list(chain(*m.values()))
			if lang in langs:
				for idx in m:
					v = m[idx]
					if (isinstance(v, list) and lang in v) or lang == v:
						key = idx
						break
		if key:
			cmap = self.rex_compiler_map
			return (key, cmap[key]) if key in cmap.keys() else key
		return False

	async def code_api(self, lang:str, code:str, fmt:bool=True):
		lang = self.get_lang(lang)
		if not lang:
			return False, '\N{NO ENTRY} `Invalid Language.`'
		code = await self.cleanup_code(code)
		payload = aiohttp.FormData()
		if isinstance(lang, tuple):
			payload.add_field('CompilerArgs', lang[1])
			lang = lang[0]
		payload.add_field('LanguageChoice', str(lang))
		# payload.add_field('EditorChoiceWrapper', 1)
		payload.add_field('Program', code)
		# payload.add_field('IsInEditMode', False)
		# payload.add_field('IsLive', False)
		# payload.add_field('ShowWarnings', False)
		r = await self.proxy_request('post',
			'https://rextester.com/rundotnet/api',
			 data=payload, json=True,
		)
		if r:
			if not r['Result'] and not r['Errors']:
				return False, 'Empty Response'
			output = r['Result'] or r['Errors'] or r['Warnings']
			if output:
				#Rex/print functions add new line for results at end
				if output.endswith('\n'):
					output = output[:-1]
				if fmt:
					output = self.format_code(output)
				output = re.sub("\u202E", "", output) # get rid of known baddies from result.
				return output, r['Stats']
		else:
			return False, f'\N{WARNING SIGN} `{self.rex_map[lang][0]}` execution failed.'
	#RE-ENABLE CODE REVIEWING AT THIS POINT

	def save_image(self, img, ext:str='png'):
		b = BytesIO()
		try:
			img.save(b, ext)
		except:
			return False
		b.seek(0)
		return b

	async def merge_images(self, imgs, method=1, vertical=False):
		ep = "merge"
		if method > 1:
			ep += str(method)

		return await self.generic_api(
			ep, urls=json.dumps(imgs),
			vertical=int(vertical)
		)
		# return await self.loop.run_in_executor(
		# 	None, getattr(self, f'do_merge_images{method}'),
		# 	imgs, vertical
		# )

	async def check_cooldown(self, bucket, ctx, msg, check=False):
		bucket = self.buckets[bucket].get_bucket(ctx)
		r = bucket.is_rate_limited()
		check = r if check else not r
		if check:
			await ctx.send(msg.format(r))

	@staticmethod
	def check_perms(obj, **perms):
		return all(getattr(obj, x, None) == perms[x] for x in perms)

	# Imitate discord clients algo
	def get_default_channel(self, user, guild, **kwargs):
		channels = [x for x in guild.channels if isinstance(x, discord.TextChannel) \
								and self.check_perms(x.permissions_for(user),
								read_messages=True, **kwargs)]
		if channels:
			return sorted(channels, key=lambda x: x.position)[0]

	def get_member(self, uid:int):
		return dget(self.bot.get_all_members(), id=uid)

	def get_user(self, uid:int):
		return dget(self.bot.users, id=uid)

	def format_time(self, obj):
		return obj.strftime('%m/%d/%Y %H:%M:%S')

	async def git_update(self):
		print(await self.run_process(['git', '-C', '/discord/', 'pull'], True))
		await self.update_release()

	async def hastebin(self, content:str, host='hb.wrmsr.io'):
		load = await self.post_data(f'https://{host}/documents', content, json=True, timeout=15)
		if load and 'key' in load:
			return f"https://{host}/{load['key']}"

	@staticmethod
	def get_role_color(user):
		default = discord.Color.default()
		d = discord.Color(0xffffff)
		if not hasattr(user, 'roles'):
			return d
		color_roles = [x for x in user.roles if x.color != default]
		if not color_roles:
			return d
		for role in sorted(user.roles, reverse=True, key=lambda x: x.position):
			if role.color != default:
				return role.color

	# Check if something is similar to a snowflake (for 2018 and a while after that)
	@staticmethod
	def is_id(n:str):
		return n.isdigit() and 15 <= len(n) <= 22

	async def store_cache(self, key, data, expiration=None):
		api = f"{self.imis_host}/{key}"
		headers = {'Authorization': 'apple_juice'}
		if expiration:
			headers['X-Delete-After'] = str(expiration)
		assert await self.post_data(api, data, headers=headers), \
					 "Piping failed, cache miss."
		return api

	async def update_release(self, first_run=False):
		ch = await self.run_process([
			'git', '-C', '/discord/', 'rev-parse', 'HEAD'
		], True)

		# It's too early, THE CORE isn't loaded yet.
		if not first_run:
			sentry_sdk.init(dsn=self.dsn, release=ch)

		self.release = ch

	# Commit hash changes as we run update commands.
	@property
	def release(self):
		return self._release

	@release.setter
	def release(self, x):
		self._release = x


def setup(bot):
	bot.add_cog(Funcs(bot))
