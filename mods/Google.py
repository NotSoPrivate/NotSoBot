import asyncio
import json
import random
import re
import shlex
from argparse import ArgumentParser
from base64 import b64encode
from urllib.parse import quote, unquote
# from urllib.parse parse_qs, urlparse
from unicodedata import normalize

from lxml import etree

import aiohttp
from async_timeout import timeout as Timeout
from discord import Embed
from discord.ext import commands
from mods.cog import Cog
from utils import checks
from utils.paginator import Pages, ReverseImagePages, CannotPaginate


class Google(Cog):
	def __init__(self, bot):
		super().__init__(bot)

		self.get_deep_text = bot.funcs.get_deep_text
		self.get_json = bot.get_json
		self.get_text = bot.get_text
		self.bytes_download = bot.bytes_download
		self.get_images = bot.get_images
		self.proxy_request = bot.funcs.proxy_request
		self.post_data = bot.post_data
		self.f_api = bot.funcs.f_api
		self.get_key = bot.funcs.get_key
		self.extension_checks = bot.funcs.extension_checks
		self.format_code = bot.funcs.format_code

		self.scrap_regex = re.compile(',"ou":"([^`]*?)"')

		with open(bot.funcs.discord_path('utils/keys.txt')) as f:
			self.keys = f.read().split('\n')

		with open(bot.funcs.discord_path('utils/rendertron.txt')) as f:
			self.rts = f.read().split('\n')

		self.youtube_cache = {}

		# Hard coded key incase of scraping failure
		self.gcv_key = "AIzaSyAa8yy0GdcGPHdtD083HiGGx_S0vMPScDM"
		bot.loop.create_task(self._get_gc_key())


	# Scrape Google's JS for demo API Key
	async def _get_gc_key(self):
		url = "https://explorer.apis.google.com/embedded.js"
		code = await self.get_text(url)
		if code:
			match = re.search(r'this\.hg=\"(.*?)\"', code)
			if match != None:
				self.gcv_key = match.group(1)

	def filter_images(self, images:list, raw=True):
		if raw:
			pred = lambda url: not url.startswith('x-raw-image://') \
											and not url.endswith(('.svg', '.bmp', '.ico', '.tiff')) \
											and any(x(unquote(url)) for x in self.extension_checks)
			return list(filter(pred, images))

		imgs = []
		for i in images:
			img = i['image']
			if img['extension'] in ('svg', 'bmp', 'ico', 'tiff'):
				url = i['thumbnail']['url']
			else:
				url = img['url']
			imgs.append(url)

		return imgs

	def get_searches(self, root, descs=False):
		search_nodes = root.findall(".//div[@class='rc']")
		results = []
		for node in search_nodes:
			url_node = node.find("./div[@class='r']/a")
			if url_node is None:
				continue
			h3 = url_node.find('h3')
			title = h3.text
			if title is None:
				title = h3.find('div')
				if title is None:
					title = h3.find('span').text
			result = [title, url_node.get('href').replace(")", "%29")]
			if descs:
				desc_node = node.find('.//div[@class="s"]/div/span')
				desc = normalize("NFKD", self.get_deep_text(desc_node))
				result.append(desc)
			results.append(result)
		return results

	async def google_scrap(self, search:str, safe=True, image=False, raw=False):
		try:
			if image:
				# api = "https://www.google.com/search?hl=en&tbm=isch&source=hp&gs_l=img&lr=lang_en&hl=en" \
				# 			f"&q"
				# # body = await self.get_text(api, timeout=20)
				# body = await self.proxy_request('get', api, text=True, timeout=20)
				# assert body
				# match = self.scrap_regex.findall(body)
				# assert match
				# return match[:100]

				api = "https://beta.notsobot.com/api/google/search/images?" \
							f"query={quote(search)}&safe={'true' if safe else 'false'}&max_results=30"
				body = await self.get_json(api, timeout=10)
				if not body:
					api = "https://www.googleapis.com/customsearch/v1?" \
								f"key={self.gcv_key}&cx=015418243597773804934:it6asz9vcss" \
								f"&searchType=image&num=10&q={quote(search)}"
					headers = self.get_headers("https://www.googleapis.com")
					body = await self.get_json(api, headers=headers, timeout=10)
					assert body and 'items' in body
					urls = [x['link'] for x in body['items']]
				else:
					urls = self.filter_images(body, raw=False)
				return urls

			# api = f"https://www.google.com/search?q={quote(search)}&safe={'on' if safe else 'off'}&num=30"
			search = search.replace('+', '\N{FULLWIDTH PLUS SIGN}')
			for _ in range(3):
				tron = self.get_key('tron', self.rts)
				api = f"http://{tron}/render/" \
							f"https://www.google.com/search%3Fq={quote(search)}%26safe={'on' if safe else 'off'}" \
							r"%26num=30%26lr=lang_en%26hl=en"
				body = await self.get_text(api, timeout=20)
				if body:
					break
			# for _ in range(5):
			# 	body = await self.proxy_request('get', api, text=True, timeout=20)
			# 	if body and "detected unusual traffic" not in body:
			# 		break
			if raw:
				return body
			assert body
			root = etree.fromstring(body, etree.HTMLParser(collect_ids=False))
			card_node = root.xpath(".//div[contains(@class, 'vk_c ') " \
															"or @class='g mnr-c g-blk' " \
															"or contains(@class, 'kp-blk')]")
															# "or contains(@class, 'kappbar')]") - timeline
			if card_node:
				card = self.parse_google_card(card_node[0])
			else:
				card = None
			results = self.get_searches(root)
			return results, card
		except (AssertionError, asyncio.TimeoutError):
			if image:
				return False
			return False, False


	def parse_google_card(self, node):
		e = Embed(colour=0x738bd7)

		# verified 1/1
		calculator = node.find(".//span[@class='cwclet']")
		if calculator is not None:
			e.title = 'Calculator'
			result = node.xpath(".//span[contains(@class, 'cwcot')]")
			if result:
				result = ' '.join((calculator.text, result[0].text.strip()))
			else:
				result = calculator.text + ' ???'
			e.description = result
			thumb = 'https://cdn.discordapp.com/attachments/178313653177548800/279860329494609920/calculator_1.png'
			e.set_thumbnail(url=thumb)
			return e

		# verified 1/1
		unit_conversions = node.xpath(".//div[@class='rpnBye']/input")
		if len(unit_conversions) == 2:
			e.title = 'Unit Conversion'
			xpath = etree.XPath("parent::div/select/option[@selected='1']/text()")
			try:
				first_node = unit_conversions[0]
				first_unit = xpath(first_node)[0]
				first_value = float(first_node.get('value'))
				second_node = unit_conversions[1]
				second_unit = xpath(second_node)[0]
				second_value = float(second_node.get('value'))
				e.description = ' '.join((str(first_value), first_unit, '=', str(second_value), second_unit))
			except:
				return None
			return e

		# verified 1/1
		currency_selectors = node.findall(".//table[@class='qzNNJ']/tbody/tr")
		if currency_selectors:
			e.title = 'Currency Conversion'
			first_node = currency_selectors[0]
			xp = "./td/div/select/option[@selected='1']"
			first_currency = first_node.find(xp)
			second_node = currency_selectors[2]
			second_currency = second_node.find(xp)
			xp = ".//td/input[contains(@class, 'vk_gy vk_sh')]"
			try:
				first_value = first_node.xpath(xp)[0].get('value')
				second_value = second_node.xpath(xp)[0].get('value')
				values = (
					first_value,
					first_currency.text,
					f'({first_currency.text})',
					'=',
					second_value,
					second_currency.text,
					f'({second_currency.text})'
				)
				e.description = ' '.join(values)
			except:
				return None
			return e

		# unverified 1/1
		info = node.find(".//div[@class='_f2g']")
		if info is not None:
			try:
				e.title = ''.join(info.itertext()).strip()
				actual_information = info.xpath(
					"parent::div/parent::div//div[@class='_XWk' or contains(@class, 'kpd-ans')]"
				)[0]
				e.description = ''.join(actual_information.itertext()).strip()
			except:
				return None
			return e

		# verified 1/1
		translation = node.find(".//div[@id='tw-ob']")
		if translation is not None:
			src_text = translation.find(".//pre[@id='tw-source-text']/span")
			src_lang = translation.find(".//select[@id='tw-sl']/option[@selected='1']")
			dest_text = translation.find(".//pre[@id='tw-target-text']/span")
			dest_lang = translation.find(".//select[@id='tw-tl']/option[@selected='1']")
			e.title = 'Translation'
			try:
				e.add_field(name=src_lang.text, value=src_text.text, inline=True)
				e.add_field(name=dest_lang.text, value=dest_text.text, inline=True)
			except:
				return None
			return e

		# verified 1/1
		if "Local Time" in self.get_deep_text(node.getparent()):
			time = node.findall("div")
			try:
				date = "".join(time[1].itertext()).strip()
				e.title = node.find('span').text
				e.description = f'{time[0].text}\n{date}'
			except:
				return None
			return e

		# unverified 1/1
		# time = node.find("./div/div[@class='vk_bk vk_ans _nEd']")
		# if time is not None:
		# 	converted = "".join(time.itertext()).strip()
		# 	try:
		# 		parent = time.getparent()
		# 		parent.remove(time)
		# 		original = "".join(parent.itertext()).strip()
		# 		e.title = 'Time Conversion'
		# 		e.description = f'{original}...\n{converted}'
		# 	except:
		# 		return None
		# 	return e

		# verified 7/4
		definition = node.xpath(".//div[contains(@id, 'uid_')]//div[contains(@class, 'lr_dct_ent vmod')]")
		if definition:
			definition = definition[0]
			try:
				e.title = definition.find("./div//span").text
				definition_info = definition.findall("./div[@class='vmod']/div")
				e.description = self.get_deep_text(node.find(".//div[@class='lr_dct_ent_ph']/span"))

				for category in definition_info:
					try:
						lexical_category = category.find("./div[@class='lr_dct_sf_h']/i/span").text
						definitions = category.findall(".//ol/li/div[@class='vmod']//div[@data-dobid='dfn']/span")
						body = []
						for index, definition in enumerate(definitions, 1):
							body.append(f'{index}. {definition.text}')
						e.add_field(name=lexical_category, value='\n'.join(body), inline=False)
					except:
						continue

			except:
				return None
			return e

		# verified 1/1
		weather = node.find(".//div[@id='wob_loc']")
		if weather is not None:
			date = node.find(".//div[@id='wob_dts']")
			category = node.find(".//img[@id='wob_tci']")
			xpath = etree.XPath(".//div[@id='wob_d']//div[contains(@class, 'vk_bk')]//span[@class='wob_t']")
			temperatures = xpath(node)
			misc_info_node = node.find(".//div[@class='vk_gy vk_sh wob-dtl']")
			if misc_info_node is None:
				return None
			precipitation = misc_info_node.find("./div/span[@id='wob_pp']")
			humidity = misc_info_node.find("./div/span[@id='wob_hm']")
			wind = misc_info_node.find("./div/span/span[@id='wob_tws']")
			try:
				e.title = 'Weather for ' + weather.text.strip()
				e.description = f'*{category.get("alt")}*'
				e.set_thumbnail(url=f"https:{category.get('src')}")
				if len(temperatures) == 4:
					first_unit = temperatures[0].text + temperatures[2].text
					second_unit = temperatures[1].text + temperatures[3].text
					units = f'{first_unit} | {second_unit}'
				else:
					units = 'Unknown'
				e.add_field(name='Temperature', value=units, inline=False)
				if precipitation is not None:
					e.add_field(name='Precipitation', value=precipitation.text)
				if humidity is not None:
					e.add_field(name='Humidity', value=humidity.text)
				if wind is not None:
					e.add_field(name='Wind', value=wind.text)
			except:
				return None
			return e

		# broken 1/1
		# quick_search = node.find(".//div[@class='xpdopen']/div[1]")
		# release = None
		# timeline = None
		# if quick_search is not None:
		# 	timeline = quick_search.find("./div/div[@class='mod']/div[@class='_l6j']")
		# 	release_body = quick_search.xpath(
		# 		".//div[@class='kp-header']/div[contains(@class, 'kp-rgc') or @class='kp-hc']"
		# 	)
		# 	if timeline is not None:
		# 		quick_search = None
		# 	elif release_body:
		# 		release_body = release_body[0]
		# 		release = quick_search
		# 		quick_search = None

		# if release is not None:
		# 	try:
		# 		title = ' '.join(quick_search.xpath(
		# 			"./div/div[contains(@class, 'mod')]"
		# 			)[0].itertext()).strip()
		# 	except:
		# 		e.title = 'Date info'
		# 	else:
		# 		e.title = title
		# 	try:
		# 		description = '\n'.join(release_body.xpath(
		# 			".//div[contains(@class, 'kno-fb-ctx')]/div"
		# 		)[0].itertext()).strip()
		# 	except:
		# 		return None
		# 	e.description = description
		# 	thumbnail = node.xpath(".//a/g-img/img[starts-with(@alt, 'Image result for')]/ancestor::a")
		# 	if thumbnail:
		# 		e.set_thumbnail(url=parse_qs(urlparse(thumbnail[0].attrib['href']).query)['imgurl'][0])
		# 	return e

		# if timeline is not None:
		# 	try:
		# 		title = timeline.find("./div[@class='_NZg']").text
		# 		table = timeline.find("./div/table/tbody")
		# 		body = []
		# 		for row in table:
		# 			body.append(' - '.join(row.itertext()).strip())
		# 	except:
		# 		return None
		# 	e.title = title
		# 	lf = '\n'
		# 	e.description = f'*{body[0]}*\n{lf.join(body[1:])}'
		# 	return e

		# if quick_search is not None:
		# 	try:
		# 		title_node = quick_search.find("./div/div[@class='g']//a")
		# 		if title_node is not None:
		# 			title = title_node.text
		# 			url = title_node.attrib['href']
		# 			summary = ''.join(quick_search.find(
		# 				"./div/div[@class='mod']/div[@class='_oDd']/span[@class='_Tgc']"
		# 			).itertext()).strip()
		# 			image = quick_search.find("./div/div[@class='_tN _VCh _WCh _IWg mod']//a[@class='bia uh_rl']")
		# 			thumbnail = parse_qs(urlparse(image.attrib['href']).query)['imgurl'][0] \
		# 									if image is not None else None
		# 		else:
		# 			title_node = quick_search.find("./div/div[@class='_tN _IWg mod']/div[@class='_f2g']")
		# 			title = ' '.join(title_node.itertext()).strip()
		# 			body_node = quick_search.find("./div/div[@class='kp-header']//a")
		# 			summary = body_node.text
		# 			url = f'https://www.google.com{body_node.attrib["href"]}'
		# 			thumbnail = None
		# 	except:
		# 		return None
		# 	e.title = title
		# 	e.url = url
		# 	e.description = summary
		# 	if thumbnail:
		# 		e.set_thumbnail(url=thumbnail)
		# 	return e

		return None

	@commands.command(aliases=['go', 'googl', 'gogle', 'g'])
	@commands.cooldown(2, 3, commands.BucketType.guild)
	async def google(self, ctx, *, search:str):
		"""Search the largest search engine on the internet"""
		level = await self.google_safety(ctx.message, True)
		urls, card = await self.google_scrap(search, True if level != 'off' else False, False)
		if not urls and not card:
			return await ctx.send("\N{WARNING SIGN} `Invalid Search.`")
		try:
			p = Pages(ctx, embed=card, color=0x738bd7,
								google=bool(card), entries=[f'**{x[0]}**\n{x[1]}' for x in urls],
								per_page=3, method=2)
			if card is None:
				p.embed.title = 'Google Search Results'
			p.embed.set_author(
				name=ctx.author.display_name,
				icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url
			)
			await p.paginate()
		except CannotPaginate:
			more = '\n'.join([f'<{x[1]}>' for x in urls[1:4]])
			await ctx.send(f'**{urls[0][0]}**\n{urls[0][1]}\n\n__More Results__\n{more}')


	@commands.command(aliases=['g2'])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def google2(self, ctx, *, search:str):
		"""Search the largest search engine on the internet and return a simpler response"""
		level = await self.google_safety(ctx.message, True)
		urls, _ = await self.google_scrap(search, True if level != 'off' else False, False)
		if not urls:
			return await ctx.send("\N{WARNING SIGN} `Invalid Search.`")
		more = '\n'.join([f'<{x[1]}>' for x in urls[1:4]])
		await ctx.send(f'**{urls[0][0]}**\n{urls[0][1]}\n\n__More Results__\n{more}')

	async def google_safety(self, message, s=False):
		if message.guild is None:
			if s:
				return 'off'
			return 1, False
		sql = f'SELECT * FROM `google_nsfw` WHERE guild={message.guild.id}'
		q = await self.cursor.execute(sql)
		result = await q.fetchone()
		if not result:
			if message.channel.is_nsfw():
				if s:
					return 'off'
				return 1, False
			else:
				if s:
					return 'medium'
				return 2, False
		level = int(result['level'])
		if s:
			if level == 1:
				return 'off'
			elif level == 2:
				return 'medium'
			elif level == 3:
				return 'high'
		return level


	@commands.command(aliases=['im', 'photo', 'img'])
	@commands.cooldown(2, 3, commands.BucketType.guild)
	async def image(self, ctx, *, search:str):
		"""Search for an image on Google"""
		level = await self.google_safety(ctx.message, True)
		load = await self.google_scrap(search, True if level != 'off' else False, True)
		if not load:
			return await ctx.send("\N{WARNING SIGN} `Invalid Search (Maybe try again?).`")
		# images = self.filter_images(load)
		try:
			p = Pages(ctx, entries=load, images=True, minimal=True, method=2)
			p.embed.title = 'Image Search Results'
			p.embed.color = 0x738bd7
			p.embed.set_author(
				name=ctx.author.display_name,
				icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url
			)
			await p.paginate()
		except CannotPaginate:
			image = random.choice(load[:4])
			await ctx.send(image)


	@commands.command(aliases=['im2', 'photo2', 'img2'])
	@commands.cooldown(5, 3, commands.BucketType.guild)
	async def image2(self, ctx, *, search:str):
		"""Search for an image on Google\nSecond response method"""
		level = await self.google_safety(ctx.message, True)
		load = await self.google_scrap(search, True if level != 'off' else False, True)
		if load:
			await ctx.send(random.choice(load[:5]))
		else:
			await ctx.send("\N{WARNING SIGN} `Invalid Search.`")


	#when did i write this???
	@commands.command(aliases=['googlesafety', 'saftey'])
	@commands.guild_only()
	@checks.mod_or_perm(manage_guild=True)
	async def safety(self, ctx, level:str=None):
		s = await self.google_safety(ctx.message)
		current_level = s[0] if not isinstance(s, (str, int)) else s
		check = s[1] if not isinstance(s, (str, int)) else True
		levels = [0, 1, 2, 3]
		if current_level == 1:
			msg = 'OFF'
		elif current_level == 2:
			msg = 'MEDIUM'
		elif current_level == 3:
			msg = 'HIGH'
		if level is None:
			return await ctx.send(
				f'\N{INFORMATION SOURCE} Current google safety level: `{current_level}` *{msg}*'
			)
		level = level.lower()
		if level.isdigit() and int(level) in levels:
			level = int(level)
		elif level == 'off' or level == 'disable':
			level = 1
		elif level == 'low' or level == 'medium':
			level = 2
		elif level == 'high':
			level = 3
		if level not in levels:
			return await ctx.send('\N{NO ENTRY} `Invalid level.`')
		if level == 0 or level == 1:
			level = 1
			smsg = 'OFF'
		elif level == 2:
			smsg = 'MEDIUM'
		elif level == 3:
			smsg = 'HIGH'
		if current_level == level:
			return await ctx.send('\N{NO ENTRY} Google Safety is already at that level!')
		if check is False:
			sql = 'INSERT INTO `google_nsfw` (`guild`, `level`) VALUES (%s, %s)'
			await self.cursor.execute(sql, (ctx.guild.id, level))
			await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Set google safety level to **{level}**')
		else:
			sql = f'UPDATE `google_nsfw` SET level={level} WHERE guild={ctx.guild.id}'
			await self.cursor.execute(sql)
			await ctx.send(
				f'\N{WHITE HEAVY CHECK MARK} Updated google safety level from **{msg}** *to* **{smsg}**'
			)


	@commands.command(aliases=['ddg'])
	@commands.cooldown(2, 3, commands.BucketType.guild)
	async def duckduckgo(self, ctx, *, search:str):
		"""Search duckduckgo.com"""
		load = await self.f_api(ctx.command.name, text=search, json=True)
		if isinstance(load, str):
			return await ctx.send(load)
		elif not load or not any(load.values()):
			return await ctx.send("\N{WARNING SIGN} `Invalid Search.`")
		urls = load['results'] if 'results' in load else None
		card = load['cards'] if 'cards' in load else {}
		ecard = Embed.from_dict(card)
		ecard.color = 0x738bd7
		try:
			p = Pages(ctx, embed=ecard, google=bool(card), per_page=3,
								entries=[f"**{x['title']}**\n{x['link']}" for x in urls])
			if card is None and not p.embed.title:
				p.embed.title = 'DuckDuckGo Results'
			p.embed.set_author(
				name=ctx.author.display_name,
				icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url
			)
			await p.paginate()
		except CannotPaginate:
			more = '\n'.join([f"<{x['link']}>" for x in urls[1:4]])
			await ctx.send(f"**{urls[0]['title']}**\n{urls[0]['link']}\n\n__More Results__\n{more}")


	@commands.command(aliases=['ddg2'])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def duckduckgo2(self, ctx, *, search:str):
		"""Search duckduckgo.com and return a simpler response"""
		load = await self.f_api('duckduckgo', text=search, json=True)
		if isinstance(load, str):
			return await ctx.send(load)
		elif not load:
			return await ctx.send("\N{WARNING SIGN} `Invalid Search.`")
		urls = load['results']
		more = '\n'.join([f"<{x['link']}>" for x in urls[1:4]])
		await ctx.send(f"**{urls[0]['title']}**\n{urls[0]['link']}\n\n__More Results__\n{more}")


	@commands.command(aliases=['ddgi', 'im3', 'photo3', 'img3'])
	@commands.cooldown(2, 3, commands.BucketType.guild)
	async def duckduckgoimage(self, ctx, *, search:str):
		"""Search for an image on DuckDuckGo"""
		load = await self.f_api('duckduckgoimages', text=search, json=True)
		if isinstance(load, str):
			return await ctx.send(load)
		elif not load:
			return await ctx.send("\N{WARNING SIGN} `Invalid Search (Maybe try again?).`")
		try:
			p = Pages(ctx, entries=load, images=True, minimal=True, method=2)
			p.embed.title = 'Image Search Results'
			p.embed.color = 0x738bd7
			p.embed.set_author(
				name=ctx.author.display_name,
				icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url
			)
			await p.paginate()
		except CannotPaginate:
			image = random.choice(load[:3])
			await ctx.send(image)


	@commands.command(aliases=['ddgi2', 'im4', 'photo4', 'img4'])
	@commands.cooldown(5, 3, commands.BucketType.guild)
	async def duckduckgoimage2(self, ctx, *, search:str):
		"""Search for an image on DuckDuckGo\nSecond response method"""
		load = await self.f_api('duckduckgoimages', text=search, json=True)
		if load:
			if isinstance(load, str):
				await ctx.send(load)
			else:
				await ctx.send(random.choice(load[:3]))
		else:
			await ctx.send("\N{WARNING SIGN} `Invalid Search.`")


	async def youtube_scrap(self, search:str, safety=False):
		try:
			headers = {
				'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:43.0) Gecko/20100101 Firefox/43.0'
			}
			search = quote(search)
			api = 'https://www.youtube.com/results?search_query={0}'.format(search)
			cookies = {'PREF': 'cvdm=grid&al=en&f4=4000000&f5=30&f1=50000000&f2=8000000'} if safety else None
			async with aiohttp.ClientSession(cookies=cookies) as session:
				with Timeout(5):
					async with session.get(api, headers=headers) as r:
						assert r.status == 200
						txt = await r.text()
			root = etree.fromstring(txt, etree.HTMLParser(collect_ids=False))
			search_nodes = root.findall(".//ol[@class='section-list']/li/ol[@class='item-section']/li")
			if not search_nodes:
				return False
			search_nodes.pop(0)
			result = False
			for node in search_nodes:
				if result:
					break
				try:
					url_node = node.find('div/div/div/h3/a')
					if url_node is None:
						continue
					title = self.get_deep_text(url_node)
					url = f"https://www.youtube.com/{url_node.attrib['href']}"
					result = (title, url)
				except:
					continue
			return result
		except:
			return False

	@commands.command(aliases=['yt', 'video'])
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def youtube(self, ctx, *, search:str):
		level = await self.google_safety(ctx.message, True)
		in_cache = False
		if search in self.youtube_cache:
			load_level = self.youtube_cache[search][1]
			if load_level <= level:
				load = self.youtube_cache[search][0]
				in_cache = True
		try:
			if not in_cache:
				key = self.get_key('google', self.keys)
				api = "https://www.googleapis.com/customsearch/v1?" \
							f"key={key}&cx=015418243597773804934:cdlwut5fxsk&q={quote(search)}"
				load = await self.get_json(api)
				assert 'error' not in load and 'items' in load
				assert load
			rand = load['items'][0]
			link = rand['link']
			title = rand['title']
			snip = rand['snippet']
			await ctx.send(f'**{title}**\n`{snip}`\n{link}')
			self.youtube_cache[search] = [load, level]
		except AssertionError:
			scrap = await self.youtube_scrap(search, True if level != 'off' else False)
			if scrap:
				title = scrap[0]
				url = scrap[1]
				await ctx.send(f"**{title}**\n{url}")
			else:
				await ctx.send("\N{WARNING SIGN} `Invalid Search`")

	@staticmethod
	def get_bar(n, total=100, bars=30):
		frac = round(n) / total
		bar_length, _ = divmod(int(frac * bars * 10), 10)
		bar = '#' * bar_length # pylint: disable=C0102
		return bar + ' ' * max(bars - bar_length, 0)


	@staticmethod
	def get_headers(origin):
		return {
			"Referer": "https://content-vision.googleapis.com/static/proxy.html",
			"Origin": origin,
			"x-origin": "https://explorer.apis.google.com",
			"Content-Type": "application/json",
			"Sec-Metadata": 'destination="", target=subresource, site=cross-site'
		}

	async def gcv_request(self, url, feature, max_results=None, force=False):
		if not force and isinstance(url, str):
			b = await self.bytes_download(url, proxy=True)
		else:
			b = url

		api = "https://content-vision.googleapis.com/v1p3beta1/" \
					f"images:annotate?alt=json&key={self.gcv_key}"
		data = {
			"requests": [
				{
					"image": {},
					"features": [
						{
							"type": feature,
							"maxResults": max_results
						},
					]
				}
			]
		}

		img = data['requests'][0]['image']
		if force:
			img['source'] = {'imageUri': b}
		else:
			img['content'] = b64encode(b.read()).decode()

		headers = self.get_headers("https://content-vision.googleapis.com")
		return await self.post_data(
			api, json.dumps(data),
			headers=headers, json=True, timeout=10
		)

	@commands.command()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def labels(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		r = await self.gcv_request(get_images[0], "LABEL_DETECTION", 35)
		if not r or not r['responses'][0]:
			return await ctx.send("\N{NO ENTRY} `Google Vision API returned an error.`")
		labs = r['responses'][0]['labelAnnotations']
		msg = "```xl\n"
		for lab in labs:
			sc = lab['score'] * 100
			desc = lab['description'].title()
			msg += f"[{self.get_bar(sc)}] {round(sc, 1)}% {desc}\n"
		await ctx.send(msg + "```")


	@commands.command(aliases=['isnsfw', 'safelabels'])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def slabels(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		r = await self.gcv_request(get_images[0], "SAFE_SEARCH_DETECTION")
		if not r or not r['responses'][0]:
			return await ctx.send("\N{NO ENTRY} `Google Vision API returned an error.`")
		load = r['responses'][0]['safeSearchAnnotation']
		e = Embed()
		e.title = "Safe Search Detection"
		e.description = "Likeliness values are " \
			"`Unknown, Very Unlikely, Unlikely, Possible, Likely, and Very Likely`"
		for title, value in load.items():
			e.add_field(name=title.title(), value=value, inline=True)
		e.timestamp = ctx.message.created_at
		e.set_author(
			name=ctx.author.display_name,
			icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url
		)
		icon = "https://cloud.google.com/images/products/vision/detect-explicit-content.png"
		e.set_footer(text='Powered by Google Vision', icon_url=icon)
		await ctx.send(embed=e)


	async def do_ocr(self, ctx, url):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		r = await self.gcv_request(get_images[0], "TEXT_DETECTION")
		if not r:
			await ctx.send("\N{NO ENTRY} `Google Vision API returned an error.`")
			return None
		elif not r['responses'][0]:
			await ctx.send("\N{WARNING SIGN} `OCR returned no results.`")
			return None
		load = r['responses'][0]['textAnnotations']
		return load[0]['description']

	@commands.command()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def ocr(self, ctx, *, url:str=None):
		text = await self.do_ocr(ctx, url)
		if text is None:
			return
		elif len(text) < 1993:
			text = self.format_code(text, None)
		await ctx.send(text, hastebin=True)


	@commands.command(aliases=["reverseimage"])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def imgs(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		tron = self.get_key('tron', self.rts)
		api = f"http://{tron}/render/https://images.google.com/searchbyimage%3Fimage_url%3D{quote(url)}" \
					"%26encoded_image%3D%26image_content%3D%26filename%3D%26hl%3Den"
		# concurrently execute both requests to save time
		coros = (
			self.get_text(api, timeout=20),
			self.gcv_request(get_images[0], "WEB_DETECTION", 10)
		)
		fut = asyncio.gather(*coros, loop=self.bot.loop)
		await fut
		body, gcr = fut.result()
		try:
			assert body
			root = etree.fromstring(body, etree.HTMLParser(collect_ids=False))
			card_node = root.xpath('//*[@id="topstuff"]/div[@class="card-section"]')
			assert card_node is not None
		except AssertionError:
			return await ctx.send("\N{WARNING SIGN} `Invalid Search.`")

		divs = list(card_node[0])
		# div/div/.../img.src
		thumbnail = f"https:{divs[0].find('.//img').get('src')}"
		# div/br...
		size = divs[0][1].find('.//br').tail.replace('\xa0×\xa0', 'x')
		# div/a.text
		guess = divs[1][0].text
		info = f"**Image size**: `{size}`\n**Best Guess**: `{guess}`"

		results = self.get_searches(root, descs=True)
		for r in results:
			if r[2]:
				r[2] += "\n"

		try:
			images = gcr['responses'][0]['webDetection']['visuallySimilarImages']
			images = self.filter_images([x['url'] for x in images], raw=True)
		except (TypeError, KeyError): # for no results or non-200 google error
			images = []
		p = ReverseImagePages(
			ctx, images, info,
			entries=[f'**{x[0]}**\n{x[2]}{x[1]}' for x in results],
			color=0x738bd7, per_page=3, method=2
		)
		p.embed.title = 'Google Reverse Image'
		p.embed.set_thumbnail(url=thumbnail)
		p.embed.set_author(
			name=ctx.author.display_name,
			icon_url=ctx.author.avatar_url
		)
		await p.paginate()


	async def translate_request(self, text, target, source=None):
		api = "https://translation.googleapis.com/language/translate/v2" \
					f"?key={self.gcv_key}"
		data = json.dumps({
			"q": text,
			"target": target,
			"source": source,
			"format": "text"
		})
		headers = self.get_headers("https://translation.googleapis.com")
		return await self.post_data(
			api, data, headers=headers,
			json=True, timeout=10
		)

	@staticmethod
	def parse_translate_source(text):
		source = None
		if '-source' in text:
			parser = ArgumentParser()
			parser.add_argument('-source')
			split = shlex.split(text)
			try:
				source = parser.parse_known_args(split)[0].source
				if source is not None:
					text = text.replace(f' -source {source}', '')
			except SystemExit:
				# temp fix to prevent this from crashing the bot
				source = None

		return source, text

	async def do_translate(self, ctx, target, text, source):
		translated = await self.translate_request(text, target, source)
		if translated is not False and translated.get('error'):
			# Probably gave an invalid language target/source
			await ctx.send("\N{WARNING SIGN} `Invalid Target or Source.`")
			return

		translated = translated['data']['translations'][0]
		src = source or translated["detectedSourceLanguage"]
		return translated["translatedText"], src

	@commands.command(aliases=["tr"])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def translate(self, ctx, target, *, text:str):
		"""Translates text.
		translate [target language] [text]
		Use the -source [source language] flag to set a source language.
		"""
		src, text = self.parse_translate_source(text)

		translated = await self.do_translate(ctx, target, text, src)
		if translated is None:
			return

		translated, src = translated
		await ctx.send(f'Translated `{src}` -> `{target}` ```{translated}```')


	@commands.command(aliases=["ocrtr", "trocr", "translateocr"])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def ocrtranslate(self, ctx, target, *, url:str=None):
		"""OCR then Translate text.
		ocrtranslate [target language] [image]
		Use the -source [source language] flag to set a source language.
		"""
		if url is not None:
			source, text = self.parse_translate_source(url)
		else:
			source = None

		text = await self.do_ocr(ctx, url)
		if text is None:
			return

		translated = await self.do_translate(ctx, target, text, source)
		if translated is None:
			return

		translated, src = translated
		await ctx.send(f'Translated `{src}` -> `{target}` ```{translated}```')


def setup(bot):
	bot.add_cog(Google(bot))
