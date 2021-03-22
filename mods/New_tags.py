import asyncio
import random
import re
from typing import Callable
from urllib.parse import quote

from dataclasses import dataclass, field
from discord.ext import commands
from utils import checks

# NSL tag exceptions

class TagError(Exception): pass
class TagScriptError(Exception): pass
# class TagFindError(Exception): pass


# NSL State

@dataclass()
class TagWork:
	args: tuple
	ctx: commands.Context
	body: str
	max_iterations: int
	variables: dict = field(default_factory=dict)
	attachments: list = field(default_factory=list)
	iscripts: list = field(default_factory=list)
	iterations:int = 0


@dataclass()
class ScriptArgs:
	default: str
	full_args: str
	invoked: str
	args: list
	preparsed: bool
	parse: TagWork
	ctx: commands.Context
	p: Callable[[str], str]


@dataclass()
class ParseResult:
	text: str = ""
	attachments: list
	iscripts: list


# NSL Parser

class Parser:
	# Optional arg: Tags. This is the tags instance. It is used for rextester.
	def __init__(self, cog):
		self.cog = cog
		self.ScriptTags = ScriptTags.ScriptTags

	# Ye Olde Scripteth Tage Splitter
	@staticmethod
	def special_split(text):
		spl = []
		depth = 0
		i = 0
		lastVB = -1
		# Search for first colon
		while i < len(text):
			if text[i] == ':':
				lastVB = i + 1
				spl.append(text[:i])
				break
			i += 1
		if i == len(text):
			return [text]
		# Split string by vertical bars
		c = ""
		while i < len(text):
			c = text[i]
			if c == '{':
				depth += 1
			else:
				if c == '}':
					depth -= 1
				else:
					if depth == 0 and c == '|':
						spl.append(text[lastVB:i])
						lastVB = i + 1
			i += 1
		if lastVB == -1:
			spl.append(text)
		else:
			spl.append(text[lastVB:])
		return spl

	# Parses script tag body
	async def execute(self, body, work):
		if not body:
			return ""

		# Preparse
		preparsed = False
		if body[0] == '!':
			work.body = body[1:]
			body = await self.parse_inner(work)
			preparsed = True

		# Split ST body
		spl = self.special_split(body)
		invoked = spl[0].strip().lower()
		args = spl[1:] if len(spl) > 1 else []

		# Inner parse shortcut for script tags
		async def p(text):
			if preparsed:
				return text
			work.body = text
			return await self.parse_inner(work)

		st_args = ScriptArgs(
			f"{{{body}}}",
			"|".join(args),
			invoked, args,
			preparsed, work,
			work.ctx, p
		)

		# Find and execute ST
		if invoked in self.ScriptTags:
			st = self.ScriptTags[invoked]
			result = st(st_args)
			if asyncio.iscoroutinefunction(result):
				result = await result
			return result or "" # ST result

		# ST not found: Try rex
		if self.cog.get_lang(invoked):
			try:
				r = await self.cog.code_api(invoked, st_args.full_args, fmt=False)
				return r[0] or r[1]
			except Exception as e:
				raise TagScriptError(str(e))

		# Default: ST not found
		return f"{{{body}}}"

	# Inner parser
	async def parse_inner(self, work):
		text = work.body
		if ("{" not in text) and ("}" not in text): # Not NSL: Skip parsing
			return text
		work.iterations += 1
		if work.iterations >= work.max_iterations: # Prevent hypercomplexity and forkbombs
			raise TagError("Whoa! You expect me to parse **all that shit**?")
		result = []
		buffer = []
		i = 0
		depth = 0
		c = '\0'
		while i < len(text):
			c = text[i]
			if c == '{':
				if depth > 0:
					buffer.append(c)
				depth += 1
			else:
				if depth > 0 and c == '}':
					depth -= 1
					if depth < 0:
						raise TagError(f"Unexpected {c} in \"{text}\".")
					if depth == 0: # Script tag reconstruction complete: execute ST body
						r = await self.execute("".join(buffer), work)
						if r != None and r:
							result.append(r)
						buffer = [] # Clear the buffer
					else:
						buffer.append(c)
				else:
					(buffer if depth > 0 else result).append(c)
			i += 1
		if depth > 0:
			raise TagError("} missing")
		return "".join(result)

	# el Parser grande
	async def parse(self, ctx, body:str, args:tuple, max_iterations:int=1000):
		#body = body.encode("ascii", errors="ignore").decode() # Remove unicode shit
		work = TagWork(
			args, ctx,
			body, max_iterations
		)

		inner_results = await self.parse_inner(work)
		# Begin parse, trim the results, and construct a result tuple
		return ParseResult(
			inner_results[:2000],
			work.attachments,
			work.iscripts
		)


# Script tag decorator
def script_tag(name=None, aliases=None):
	def decorator(func):
		# If "name" has been specified, that name will be used instead.
		# By default, the name of the function is the ST's primary name
		if name:
			ScriptTags.ScriptTags[name] = func
		else:
			ScriptTags.ScriptTags[func.__name__] = func

		if aliases != None:
			for c in aliases:
				ScriptTags.ScriptTags[c] = func

	return decorator


# Script tag code
# pylint: disable=E0213,E1101
class ScriptTags:
	ScriptTags = {}

	#Discord
	@script_tag(aliases=['name'])
	def user(st):
		return st.ctx.author.name

	@script_tag()
	def nick(st):
		return st.ctx.author.display_name

	@script_tag()
	def mention(st):
		return st.ctx.author.mention

	@script_tag()
	def discrim(st):
		return str(st.ctx.author.discriminator)

	@script_tag(aliases=['userid'])
	def id(st):
		return str(st.ctx.author.id)

	@script_tag()
	def avatar(st):
		return str(st.ctx.author.avatar_url)

	@script_tag(aliases=['guild'])
	def server(st):
		return st.ctx.guild.name if st.ctx.guild else "Direct Message"

	@script_tag(aliases=['guildcount', 'membercount'])
	def servercount(st):
		return str(st.ctx.guild.member_count) if st.ctx.guild  else "2"

	@script_tag(aliases=['guildid', 'sid', 'gid'])
	def serverid(st):
		return str(st.ctx.guild.id)

	@script_tag()
	def channel(st):
		return str(st.ctx.channel)

	@script_tag()
	def channelid(st):
		return str(st.ctx.channel.id) if st.ctx.channel else "0"

	# Discord (random)
	@script_tag()
	def randuser(st):
		return random.choice(list(st.ctx.guild.members)).display_name \
					 if st.ctx.guild is not None else \
					 st.ctx.author.display_name

	@script_tag()
	def randonline(st):
		return random.choice(
			[m for m in st.ctx.guild.members if m.status is discord.Status.online]
		).display_name if st.ctx.guild else st.ctx.author.display_name

	@script_tag()
	def randonlineid(st):
		return str(random.choice(
			[m for m in st.ctx.guild.members if m.status is discord.Status.online]
		).id) if st.ctx.guild else st.ctx.author.id

	@script_tag()
	def randchannel(st):
		return random.choice(list(st.ctx.guild.channels)).mention \
					 if st.ctx.guild else ""

	# Tag arguments
	@script_tag(name='args')
	def arguments(st):
		return st.p(" ".join(st.parse.args))

	@script_tag()
	def arg(st):
		if len(st.args) < 1:
			return st.default
		arg_index = int(st.p(st.args[0]))
		if arg_index >= 0 and arg_index < len(st.parse.args):
			return st.parse.args[arg_index]
		return ""

	@script_tag(aliases=['argslen'])
	def argscount(st):
		return str(len(st.parse.args))

	# Variables
	@script_tag(name="set")
	def set_(st):
		if len(st.args) < 2:
			return st.default
		st.parse.variables[st.p(st.args[0])] = st.p("|".join(st.args[1:]))
		return ""

	@script_tag()
	def get(st):
		if len(st.args) < 1:
			return st.default
		return st.parse.variables.get(st.p(st.full_args), "")

	# Code flow
	@script_tag()
	def note(st):
		return ""

	@script_tag()
	def eval(st):
		if len(st.args) < 1:
			return st.default
		return st.p(st.p(st.full_args))

	@script_tag()
	def ignore(st):
		return st.full_args

	@script_tag(name='if')
	def if_(st):
		if len(st.args) < 4:
			return st.default
		s1 = st.p(st.args[0])
		s2 = st.p(st.args[2])
		comparison = st.p(st.args[1])
		then_ = ""
		else_ = ""
		add2else = False
		for c in st.args[3:]:
			if c.startswith("then:"):
				add2else = False
				then_ += st.p(c[5:])
			elif c.startswith("else:"):
				add2else = True
				else_ += st.p(c[5:])
			else:
				t = "|" + st.p(c)
				if add2else:
					else_ += t
				else:
					then_ += t
		if comparison == "=":
			return then_ if s1 == s2 else else_
		elif comparison == "?":
			return then_ if re.search(s2, s1) else else_
		try:
			i1 = float(s1)
			i2 = float(s2)
			if comparison == "<":
				return then_ if i1 < i2 else else_
			elif comparison == "<=":
				return then_ if i1 <= i2 else else_
			elif comparison == ">":
				return then_ if i1 > i2 else else_
			elif comparison == ">=":
				return then_ if i1 >= i2 else else_
			elif comparison == "~":
				return then_ if i1 * 100 == i2 * 100 else else_
		except ValueError:
			if comparison == "~":
				return then_ if s1.lower() == s2.lower() else else_
			return else_

	# Random
	@script_tag()
	def choose(st):
		if len(st.args) < 1:
			return st.default
		return st.p(random.choice(st.args))

	@script_tag(aliases=['range', 'rnd'])
	def random(st):
		if len(st.args) < 2:
			return st.default
		try:
			arg1 = int(st.p(st.args[0]))
			arg2 = int(st.p(st.args[1]))
			return str(random.randint(arg1, arg2))
		except ValueError:
			raise TagError(f"{st.args[0]} and {st.args[1]} aren't valid numbers.")

	# String manipulation
	@script_tag()
	def upper(st):
		return (st.p(st.full_args)).upper()

	@script_tag()
	def lower(st):
		return (st.p(st.full_args)).lower()

	@script_tag(name="encode", aliases=["url"])
	def url(st):
		return quote(st.full_args)

	@script_tag(aliases=['replace', 'replaceregex', 'regex'])
	def replace(st):
		cardinal_args = ["", "", ""] # Will contain the following sequence: pattern, in, with
		addto = 0
		for i, c in enumerate(st.args):
			if c.startswith("pattern:"):
				addto = 0
				cardinal_args[0] += st.p(c[8:])
			elif c.startswith("with:"):
				addto = 1
				cardinal_args[1] += st.p(c[5:])
			elif c.startswith("in:"):
				addto = 2
				cardinal_args[2] += st.p(c[3:])
			else:
				cardinal_args[addto] += st.p(c if i == 0 else "|"+c)

		return re.sub(cardinal_args[0], cardinal_args[1], cardinal_args[2]) \
					 if st.invoked == "replaceregex" or st.invoked == "regex" else \
					 cardinal_args[2].replace(cardinal_args[0], cardinal_args[1])

	@script_tag(aliases=['len'])
	def length(st):
		return str(len(st.p(st.full_args)))

	# Mathematics
	@script_tag()
	def math(st):
		result = 0
		# This is used to set result to the first number before doing operations to it.
		setr = True
		# Mathematic operation modes: 0=addition, 1=subtraction, 2=multiplication, 3=division, 4=modulo
		op = 0
		for arg in st.args:
			argP = st.p(arg)
			if argP.isdigit():
				iarg = int(argP)
				if setr:
					result = iarg
					setr = False
				else:
					if op == 0:
						result += iarg
					elif op == 1:
						result -= iarg
					elif op == 2:
						result *= iarg
					elif op == 3:
						result /= iarg
					elif op == 4:
						result %= iarg
			elif argP == "+":
				op = 0
			elif argP == "-":
				op = 1
			elif argP == "*":
				op = 2
			elif argP == "/":
				op = 3
			elif argP == "%":
				op = 4
		return str(result)

	# Escape characterss
	@script_tag(aliases=["lb"])
	def cb(st):
		return "}"

	@script_tag(aliases=["rb"])
	def ob(st):
		return "{"

	@script_tag(aliases=["<"])
	def lt(st):
		return "<"

	@script_tag(aliases=[">"])
	def gt(st):
		return ">"

	@script_tag(aliases=["|"])
	def vb(st):
		return "|"

	@script_tag(aliases=["\\n"])
	def newline(st):
		return "\n"

	# NSFW
	@script_tag()
	def nsfw(st):
		if not st.ctx.channel.is_nsfw():
			raise checks.Nsfw()
		return ""

	# Attachments
	@script_tag()
	def attach(st):
		for c in st.args:
			st.parse.attachments.append(st.p(c))
		return ""

	@script_tag(aliases=['imagescript'])
	def iscript(st):
		for c in st.args:
			st.parse.iscripts.append(st.p(c))
		return ""

# ----- TESTING -----

from enum import Enum

# discord.py dummy code
class Context:
	def __init__(self):
		self.guild = self.Guild()
		self.author = self.guild.members[0]
		self.channel = self.Channel()

	class User:
		name = "dummy"
		display_name = "dummy nickname"
		discriminator = "0000"
		mention = name+"#"+discriminator
		id = "000000000000000000"
		def __init__(self):
			self.status = discord.Status.online

	class Guild:
		name = "Dummy Guild"
		id = "000000000000000000"
		def __init__(self):
			self.members = [ Context.User(), Context.User(), Context.User() ] # A fake server with three users

	class Channel:
		name = "channel"
		id = "000000000000000000"

class discord:
	class Status(Enum):
		online = 'online'
		offline = 'offline'
		idle = 'idle'
		dnd = 'dnd'
		do_not_disturb = 'dnd'
		invisible = 'invisible'

		def __str__(self):
			return self.value

class Tags():
	valid_langs = { 'ada', 'assembly', 'asm', 'bash', 'brainfuck', 'bf', 'c#', 'c++(gcc)', 'c++', 'cpp', 'c++(clang)', 'c++(vc++)', 'c(gcc)', 'c', 'c(clang)', 'c(vc)', 'commonlisp', 'lisp', 'd', 'elixir', 'ex', 'erlang', 'f#', 'fortran', 'fort', 'go', 'haskell', 'hs', 'java', 'javascript', 'js', 'kotlin', 'kot', 'lua', 'mysql', 'node.js', 'node', 'ocaml', 'octave', 'objective-c', 'oc', 'oracle', 'pascal', 'perl', 'php', 'php7', 'postgresql', 'psql', 'postgres', 'prolog', 'python2', 'python2.7', 'py2.7', 'py2', 'python', 'python3', 'py', 'py3', 'r', 'ruby', 'rb', 'scala', 'scheme', 'sqlserver', 'swift', 'tcl', 'visualbasic', 'vb' }
	def get_lang(self, lang):
		return lang if lang in self.valid_langs else None #idk how get_lang works so this is a dumb approximation

	async def code_api(self, lang, code, bullshit):
		return "allah permits the execution of this code"

# Testing
loop = asyncio.get_event_loop()
parser = Parser(Tags())
print(loop.run_until_complete(parser.parse(Context(), "{note:NOTES NOTES NOTES HA HA THIS WON'T BE PARSED EAT MY ASS} {set:testbed|And now here's a thing:{\\n} Args: {args}{\\n} Calculation style 1: 2+2={math:2|+|3}{\\n} Calculation style 2: 2+2={math:+|2|3}{\\n} Calculation style 3: 2+2={2+3}{\\n} first arg is \"ayy\" = {if:{arg:0}|=|ayy|then:true|else:false}{\\n} number between -100 and 100: {random:-100|100}{\\n} number between dumb and super dumb: {choose:you|not visiting ropestore.org}{\\n} upper: {upper:hey um how do i install this bot on my server}{\\n} lower: {lower:YOU FUCKING RETARD CUNT PIG DICK FIX YOUR SHIT FAGGOT NIGGER}{\\n} {ignore:{ignore:}} test. (two nested ignores). {ignore:{argslen} should have been called {argscount} tbh amirite lads}{\\n} ok i'm done kid. i bet you know nothing about hacking.} it's okay to rape {choose:in self defense|if {choose:the great prophet mohammed|your black friend|she|society|ropestore.org brand rope} {choose:permit|demand|request}s it|because technically, society has raped us all|{args} amirite boys}.{\\n}{\\n}{get:testbed}", ("hello", "world"))).text)
loop.close()

# parseResult = parser.parse(ctx, "NSL goes here: {args}", args_tuple)
# text = parseResult.text
# attachments = parseResult.attachments