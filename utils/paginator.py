import asyncio
from asyncio import FIRST_COMPLETED
from urllib.parse import quote

import discord


class CannotPaginate(Exception): pass

class Pages:
	"""Implements a paginator that queries the user for the
	pagination interface.

	Pages are 1-index based, not 0-index based.

	If the user does not reply within 2 minutes then the pagination
	interface exits automatically.

	Parameters
	------------
	bot
		The bot instance.
	message
		The message that initiated this session.
	entries
		A list of entries to paginate.
	per_page
		How many entries show up per page.

	Attributes
	-----------
	embed: discord.Embed
		The embed object that is being used to send pagination info.
		Feel free to modify this externally. Only the description,
		footer fields, and colour are internally modified.
	permissions: discord.Permissions
		Our permissions for the channel.
	"""
	def __init__(self, ctx, *, entries, **kwargs):
		self.bot = ctx.bot
		self.loop = ctx.bot.loop
		self.entries = entries
		self.message = ctx.message
		self.author = ctx.author
		self.channel = ctx.channel
		self.send = ctx.send
		self.method = kwargs.pop('method', 1)
		# self.method = 1
		if self.method == 1:
			self.add_reaction = ctx.add_reaction
			self.remove_reaction = ctx.remove_reaction
		self.per_page = kwargs.pop('per_page', 10)
		self.show_help_info = kwargs.pop('show_help_info', self.method == 2)
		self.timeout = kwargs.pop('timeout', 120)
		self.minimal = kwargs.pop('minimal', False)
		self.images = kwargs.pop('images', False)
		if self.images:
			self.per_page = 1
		self.show_zero = kwargs.pop('show_zero', True)
		self.extra_info = kwargs.pop('extra_info', None)
		self.current_page = kwargs.pop('page', 1)
		pages, left_over = divmod(len(self.entries), self.per_page)
		if left_over:
			pages += 1
		self.maximum_pages = pages
		self.owner_only = kwargs.pop('owner_only', True)
		self.google = kwargs.pop('google', False)
		if self.google:
			self.current_page = 0
		self.color = kwargs.pop('color', discord.Color.greyple())
		self.embed = kwargs.pop('embed', None)
		if self.embed is None:
			self.embed = discord.Embed()
			if self.color:
				self.embed.color = self.color
		self.descriptions = kwargs.pop('descriptions', None)
		self.paginating = len(entries) > self.per_page
		self.asking = False
		self.remove_on_react = kwargs.pop('remove_on_react', False)

		if not self.minimal:
			self.reaction_emojis = [
				# ('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.first_page),
				('\N{BLACK LEFT-POINTING TRIANGLE}', self.previous_page),
				('\N{BLACK RIGHT-POINTING TRIANGLE}', self.next_page),
				# ('\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}', self.last_page),
				('\N{INPUT SYMBOL FOR NUMBERS}', self.numbered_page),
				('\N{BLACK SQUARE FOR STOP}', self.stop_pages),
				('\N{INFORMATION SOURCE}', self.show_help)
			]
		else:
			self.reaction_emojis = [
				('\N{BLACK LEFT-POINTING TRIANGLE}', self.previous_page),
				('\N{BLACK RIGHT-POINTING TRIANGLE}', self.next_page),
				('\N{BLACK SQUARE FOR STOP}', self.stop_pages),
				('\N{INPUT SYMBOL FOR NUMBERS}', self.numbered_page)
			]

		if self.method == 2:
			self.triggers = [
				(('n', 'next', 'next page'), self.next_page),
				(('b', 'back', 'previous'), self.previous_page),
				(('s', 'stop', 'e', 'end'), self.stop_pages),
				(('f', 'first', 'first page'), self.first_page),
				(('l', 'last', 'last page'), self.last_page),
				(('h', 'help'), self.show_help),
				(('p', 'page'), self.numbered_page)
			]

		try:
			self.permissions = ctx.channel.permissions_for(ctx.me)
		except AttributeError:
			raise CannotPaginate('Please try again, bot initializing.')

		if not self.permissions.embed_links:
			raise CannotPaginate('Bot does not have `embed_links` permission.')
		elif self.method == 1 and not self.permissions.add_reactions and left_over:
			raise CannotPaginate('Bot does not have `add_reactions` permission.')

		if (self.method == 1 and not self.permissions.manage_messages) \
			 or not self.remove_on_react:
			self.bot.add_listener(self.on_raw_reaction_remove)


	def get_page(self, page):
		base = (page - 1) * self.per_page
		return self.entries[base:base + self.per_page]

	def set_description(self, p):
		if not self.images:
			self.embed.description = '\n'.join(p)

	async def show_page(self, page, *, first=False):
		if self.google and page == 0:
			self.google_embed = True
			if not isinstance(self.google, dict):
				self.google = self.embed.to_dict()
			else:
				self.embed = self.embed.from_dict(self.google)
		else:
			if self.google and self.google_embed:
				self.embed = discord.Embed(color=self.color)
				self.google_embed = False
			entries = self.get_page(page)
			p = []
			for t in enumerate(entries, 1 + ((page - 1) * self.per_page)):
				if self.images:
					self.embed.set_image(url=quote(t[1], safe="%/:=&?~#+!$,;'@()*[]"))
				else:
					p.append('%s. %s' % t)
		self.current_page = page
		if self.maximum_pages != 0 and self.show_zero:
			if self.extra_info:
				self.embed.set_footer(text='Page %s/%s (%s entries) | %s' % (page, self.maximum_pages, len(self.entries), self.extra_info))
			else:
				self.embed.set_footer(text='Page %s/%s (%s entries)' % (page + 1 if self.google else page, self.maximum_pages + 1 if self.google else self.maximum_pages, len(self.entries)))
		if self.descriptions:
			self.embed.description = self.descriptions[page - 1]
		if self.google and page > 0:
			self.embed.title = 'Google Search Results'
		if not self.paginating:
			if page != 0:
				self.set_description(p)
			return await self.send(embed=self.embed)
		if not first:
			if page != 0:
				self.set_description(p)
			try:
				return await self.message.edit(embed=self.embed)
			except discord.NotFound:
				return
		if self.show_help_info:
			h = ('',
				'Confused? React with \N{INFORMATION SOURCE} for more info.' if self.method == 1 else \
				'Confused? Reply with `h` or `help` for more info.'
			)
			if not self.images:
				if page == 0:
					j = '\n'.join(h)
					if bool(self.embed.description):
						self.embed.description = self.embed.description + j
					else:
						self.embed.description = j
				else:
					p.extend(h)
			else:
				self.embed.description = '\n'.join(h)
		if page != 0:
			self.set_description(p)
		self.message = await self.send(embed=self.embed)
		if self.method == 1:
			for (reaction, _) in self.reaction_emojis:
				if self.maximum_pages == 2 and reaction in ('\u23ed', '\u23ee'):
					continue
				await self.add_reaction(self.message, reaction)

	async def checked_show_page(self, page):
		if page <= self.maximum_pages:
			if not self.google and page == 0:
				return
			await self.show_page(page)
			return True

	async def first_page(self):
		"""goes to the first page"""
		await self.show_page(1)

	async def last_page(self):
		"""goes to the last page"""
		await self.show_page(self.maximum_pages)

	async def next_page(self):
		"""goes to the next page"""
		if self.current_page == self.maximum_pages and self.minimal:
			await self.first_page()
		else:
			await self.checked_show_page(self.current_page + 1)

	async def previous_page(self):
		"""goes to the previous page"""
		if self.current_page == 1 and self.minimal:
			await self.last_page()
		else:
			if self.current_page < 0:
				return
			await self.checked_show_page(self.current_page - 1)

	async def show_current_page(self):
		if self.paginating:
			await self.show_page(self.current_page)

	async def numbered_page(self, page=None):
		"""lets you type a page number to go to"""
		if page is None:

			if self.asking:
				return

			self.asking = True
			msg = await self.send('What page do you want to go to?')
			if self.permissions.manage_messages:
				to_delete = [msg]

			def check(m):
				ids = (self.author.id, self.bot.owner_id)
				return m.content.isdigit() and m.author.id in ids \
							 and m.channel == self.channel

			try:
				msg = await self.bot.wait_for('message', check=check, timeout=30.0)
			except asyncio.TimeoutError:
				await self.send('Took too long.', delete_after=5)
			else:
				if self.permissions.manage_messages:
					to_delete.append(msg)
					await self.channel.delete_messages(to_delete)

				self.asking = False
				page = int(msg.content)

		if page is not None and await self.checked_show_page(page) is None:
			await self.send('Invalid page given. (%s/%s)' % (page, self.maximum_pages), delete_after=5)

	async def show_help(self):
		"""shows this message"""
		e = discord.Embed()
		messages = ['Welcome to the interactive paginator!\n']
		messages.append('This interactively allows you to see pages of text by navigating with ' \
										f"{'reactions' if self.method == 1 else 'messages'}. They are as follows:\n")
		if self.method == 2:
			for trigger, func in self.triggers:
				messages.append(f"`{', '.join(trigger)}` {func.__doc__}")

			messages.append("\nMake sure the bot has `MANAGE_MESSAGES` permission " \
											"to prevent chat log spam.")
			messages.append("You can also manually add the emojis to control " \
											"the paginator; if it's out of chat view.\n\n" \
											"Emojis include: \n")

		for emoji, func in self.reaction_emojis:
			messages.append(f'{emoji} {func.__doc__}')

		e.description = '\n'.join(messages)
		e.colour =  0x738bd7 # blurple
		e.set_footer(text='We were on page %s before this message.' % self.current_page)
		try:
			await self.message.edit(embed=e)
		except discord.NotFound:
			self.paginating = False
			return

		async def go_back_to_current_page():
			await asyncio.sleep(60.0)
			await self.show_current_page()

		self.loop.create_task(go_back_to_current_page())

	async def stop_pages(self):
		"""stops the interactive pagination session"""
		try:
			await self.message.delete()
		except discord.NotFound:
			pass
		self.paginating = False

	def react_check(self, payload):
		if payload.message_id != self.message.id:
			return False

		user = payload.user_id
		if user is None or (self.owner_only and user != self.author.id and user != self.bot.owner_id):
			return False

		for (emoji, func) in self.reaction_emojis:
			if str(payload.emoji) == emoji:
				self.match = func
				return True

		return False

	def message_check(self, message):
		if message.channel != self.message.channel:
			return
		user = message.author
		if self.owner_only and user.id != self.author.id and user.id != self.bot.owner_id:
			return False
		# if (any(x[1].__self__ != self for i, x in enumerate(self.bot._listeners['message']) \
		# 	  if isinstance(x[1].__self__, Pages))):
		#get the last paginator in the channel and check if its us
		#if not stop paginating
		ls = []
		for x in self.bot._listeners['message']:
			f = x[1]
			if 'Pages' in str(f):
				l = getattr(f, '__self__', self)
				if l.message.channel == self.message.channel:
					ls.append(l)
		if ls and ls[-1] != self:
			self.paginating = False
			return False
		sp = message.content.lower().split(' ', maxsplit=1)
		if not any(sp):
			return False
		for (p, func) in self.triggers:
			for t in p:
				l = len(t)
				if sp[0][:l] == t:
					if func == self.numbered_page:
						num = None
						# ex: p 100
						if len(sp) == 2 and sp[1].isdigit():
							num = int(sp[1])
						# ex: p100
						elif len(sp[0]) > l:
							n = sp[0][l:]
							if n.isdigit():
								num = int(n)
						if num is not None:
							self.match = lambda: self.numbered_page(num)
							return True
					elif (sp[0] == t and not (len(sp) == 2 and sp[1].isalpha())) or ' '.join(sp) == t:
						self.match = func
						return True
		return False

	async def method_1(self):
		while self.paginating:
			try:
				payload = await self.bot.wait_for('raw_reaction_add', check=self.react_check, timeout=120.0)
			except asyncio.TimeoutError:
				self.paginating = False
				try:
					if self.permissions.manage_message:
						await self.message.clear_reactions()
				except:
					pass
				finally:
					break
				if self.permissions.manage_messages and self.remove_on_react:
					self.loop.create_task(self.remove_reaction(
						self.message, payload.emoji,
						discord.Object(id=payload.user_id)
					))

			await self.match()

	async def method_2(self):
		while self.paginating:
			try:
				msg = await self.bot.wait_for('message', check=self.message_check, timeout=120.0)
			except asyncio.TimeoutError:
				self.paginating = False
				break

			await self.match()

			if self.method == 2 and self.permissions.manage_messages:
				await msg.delete()

	async def paginate(self):
		"""Actually paginate the entries and run the interactive loop if necessary."""
		first_page = self.show_page(self.current_page, first=True)
		if not self.paginating:
			await first_page
		else:
			# allow us to react to reactions right away if we're paginating
			self.loop.create_task(first_page)
		coros = [self.method_1()]
		if self.method == 2:
			coros.append(self.method_2())

		await asyncio.gather(*coros, return_exceptions=False)

	async def on_raw_reaction_remove(self, payload):
		if not self.paginating:
			return self.bot.remove_listener(self.on_raw_reaction_remove)
		elif self.message is None: # ???
			return
		check = self.react_check(payload)
		if check:
			await self.match()


class ReverseImagePages(Pages):
	def __init__(self, ctx, images, info, **kwargs):
		super().__init__(ctx, **kwargs)
		self.images = images
		self.info = f"{info}\n\n"
		pages, left_over = divmod(len(self.entries), self.per_page)
		if left_over:
			pages += 1
		extra_pages = (len(self.images) - pages) + pages
		if extra_pages > pages:
			pages += extra_pages
		self.maximum_pages = pages
		self.paginating = self.paginating or len(self.images) > 1

	def get_page(self, page):
		try:
			return super().get_page(page)
		except KeyError:
			return None

	def set_description(self, p):
		self.embed.description = self.embed.description + self.info + '\n'.join(p)

	async def show_page(self, page, *, first=False):
		self.current_page = page
		entries = self.get_page(page)
		p = []

		if self.show_help_info:
			h = ('',
				'Confused? React with \N{INFORMATION SOURCE} for more info.' if self.method == 1 else \
				'Confused? Reply with `h` or `help` for more info.',
				'\n'
			)

			if not self.images:
				if page == 0:
					j = '\n'.join(h)
					if bool(self.embed.description):
						self.embed.description = self.embed.description + j
					else:
						self.embed.description = j
				else:
					p.extend(h)
					self.set_description(p)
			else:
				self.embed.description = '\n'.join(h)

		if entries is not None:
			for index, entry in enumerate(entries, 1 + ((page - 1) * self.per_page)):
				p.append(f'{index}. {entry}')

			self.set_description(p)

		if self.maximum_pages > 1:
			self.embed.set_footer(
				text='Page %s/%s (%s entries)' % (
				page, self.maximum_pages, len(self.entries)
			))

		if page <= len(self.images):
			self.embed.set_image(url=self.images[page - 1])
		else:
			self.embed.set_image(url="")

		if not self.paginating:
			return await self.send(embed=self.embed)

		if not first:
			try:
				return await self.message.edit(embed=self.embed)
			except discord.NotFound:
				self.paginating = False
				return
	
		self.message = await self.send(embed=self.embed)
		if self.method == 1:
			for (reaction, _) in self.reaction_emojis:
				if self.maximum_pages == 2 and reaction in ('\u23ed', '\u23ee'):
					continue
				await self.add_reaction(self.message, reaction)


class HelpPaginator(Pages):
	def __init__(self, help_command, ctx, entries, *, per_page=4):
		super().__init__(ctx, entries=entries, per_page=per_page)
		self.reaction_emojis.append(('\N{WHITE QUESTION MARK ORNAMENT}', self.show_bot_help))
		self.total = len(entries)
		self.help_command = help_command
		self.prefix = help_command.clean_prefix

	def get_bot_page(self, page):
		cog, description, cmds = self.entries[page - 1]
		self.title = f'{cog} Commands'
		self.description = description
		return cmds

	def prepare_embed(self, entries, page, *, first=False):
		self.embed.clear_fields()
		self.embed.description = self.description
		self.embed.title = self.title

		if self.get_page is self.get_bot_page:
			value ='For more help, join the official bot support server: https://discord.gg/9Ukuw9V'
			self.embed.add_field(name='Support', value=value, inline=False)

		self.embed.set_footer(text=f'Use "{self.prefix}help command" for more info on a command.')

		for entry in entries:
			signature = f'{entry.qualified_name} {entry.signature}'
			self.embed.add_field(name=signature, value=entry.short_doc or "No help given", inline=False)

		if self.maximum_pages:
			self.embed.set_author(name=f'Page {page}/{self.maximum_pages} ({self.total} commands)')

	async def show_help(self):
		"""shows this message"""

		self.embed.title = 'Paginator help'
		self.embed.description = 'Hello! Welcome to the help page.'

		messages = [f'{emoji} {func.__doc__}' for emoji, func in self.reaction_emojis]
		self.embed.clear_fields()
		self.embed.add_field(name='What are these reactions for?', value='\n'.join(messages), inline=False)

		self.embed.set_footer(text=f'We were on page {self.current_page} before this message.')

		try:
			await self.message.edit(embed=self.embed)
		except discord.NotFound:
			self.paginating = False
			return

		async def go_back_to_current_page():
			await asyncio.sleep(30.0)
			await self.show_current_page()

		self.loop.create_task(go_back_to_current_page())

	async def show_bot_help(self):
		"""shows how to use the bot"""

		self.embed.title = 'Using the bot'
		self.embed.description = 'Hello! Welcome to the help page.'
		self.embed.clear_fields()

		entries = (
			('<argument>', 'This means the argument is __**required**__.'),
			('[argument]', 'This means the argument is __**optional**__.'),
			('[A|B]', 'This means the it can be __**either A or B**__.'),
			('[argument...]', 'This means you can have multiple arguments.\n' \
												'Now that you know the basics, it should be noted that...\n' \
												'__**You do not type in the brackets!**__')
		)

		self.embed.add_field(name='How do I use this bot?', value='Reading the bot signature is pretty simple.')

		for name, value in entries:
			self.embed.add_field(name=name, value=value, inline=False)

		self.embed.set_footer(text=f'We were on page {self.current_page} before this message.')
		await self.message.edit(embed=self.embed)

		async def go_back_to_current_page():
			await asyncio.sleep(30.0)
			await self.show_current_page()

		self.loop.create_task(go_back_to_current_page())
