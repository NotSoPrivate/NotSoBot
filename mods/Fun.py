import asyncio
import math
import random
import re
from base64 import b64decode, b64encode
from datetime import datetime
from io import BytesIO
from lxml import etree
from string import ascii_lowercase as alphabet
from urllib.parse import quote
from uuid import uuid4

import discord
from discord.ext import commands
from aiohttp import FormData
from async_timeout import timeout as Timeout

import ujson as json
import urbandict
from imgurpython import ImgurClient
from mods.cog import Cog
from utils import checks
from utils.agarify import agarify as do_agarify
from utils.converters import MemberOrMessage
from utils.paginator import CannotPaginate, Pages


class Fun(Cog):
	def __init__(self, bot):
		super().__init__(bot)

		# locals
		self.discord_path = bot.path.discord
		self.files_path = bot.path.files
		self.bytes_download = bot.bytes_download
		self.get_json = bot.get_json
		self.truncate = bot.funcs.truncate
		self.get_images = bot.get_images
		self.get_text = bot.get_text
		self.post_data = bot.post_data
		self.generic_api = bot.funcs.generic_api
		self.f_api = bot.funcs.f_api
		self.emoji_path = bot.funcs.emoji_path
		self.png_svg = bot.funcs.png_svg
		self.merge_images = bot.funcs.merge_images
		self.proxy_request = bot.funcs.proxy_request
		self.get_deep_text = bot.funcs.get_deep_text
		self.run_process = bot.run_process
		self.get_key = bot.funcs.get_key
		self.get_role_color = bot.funcs.get_role_color
		self.is_id = bot.funcs.is_id
		self.gcv_request = bot.get_cog("Google").gcv_request

		try:
			self.imgur_client = ImgurClient("1fd3ef04daf8cab", "f963e574e8e3c17993c933af4f0522e1dc01e230")
		except:
			bot.remove_command('imgur')

		# regex
		self.emote_regex = bot.funcs.emote_regex
		self.photofunia_regex = re.compile(r"(https:.*results.*_r\.(jpg|png|gif)\?download)")

		# file loading
		self.regional_map = json.load(
			open(self.discord_path('utils/regionals.json'), encoding='utf8')
		)
		self.emojis = json.load(
			open(self.files_path('emojis.json'), encoding='utf8')
		)

		# faceapp
		self.fa_ua = "FaceApp/3.2.1 (Linux; Android 8.1)"
		self.fa_did = "208B1A02-1FEB-40C3-9434-AE3BDF308012"
		self.fa_itunes = r"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\/pn+\/8Jr9VterHNRSQhWicxDkMyOgQLQoJe2XLGhaWmHkBBoJiY5uB0Qc7AKXcVz0N92O9gt2Yge4+wHz+KO0NP6JlWB7+IDSSMCAwEAAaOCAdcwggHTMD8GCCsGAQUFBwEBBDMwMTAvBggrBgEFBQcwAYYjaHR0cDovL29jc3AuYXBwbGUuY29tL29jc3AwMy13d2RyMDQwHQYDVR0OBBYEFJGknPzEdrefoIr0TfWPNl3tKwSFMAwGA1UdEwEB\/wQCMAAwHwYDVR0jBBgwFoAUiCcXCam2GGCL7Ou69kdZxVJUo7cwggEeBgNVHSAEggEVMIIBETCCAQ0GCiqGSIb3Y2QFBgEwgf4wgcMGCCsGAQUFBwICMIG2DIGzUmVsaWFuY2Ugb24gdGhpcyBjZXJ0aWZpY2F0ZSBieSBhbnkgcGFydHkgYXNzdW1lcyBhY2NlcHRhbmNlIG9mIHRoZSB0aGVuIGFwcGxpY2FibGUgc3RhbmRhcmQgdGVybXMgYW5kIGNvbmRpdGlvbnMgb2YgdXNlLCBjZXJ0aWZpY2F0ZSBwb2xpY3kgYW5kIGNlcnRpZmljYXRpb24gcHJhY3RpY2Ugc3RhdGVtZW50cy4wNgYIKwYBBQUHAgEWKmh0dHA6Ly93d3cuYXBwbGUuY29tL2NlcnRpZmljYXRlYXV0aG9yaXR5LzAOBgNVHQ8BAf8EBAMCB4AwEAYKKoZIhvdjZAYLAQQCBQAwDQYJKoZIhvcNAQEFBQADggEBAA2mG9MuPeNbKwduQpZs0+iMQzCCX+Bc0Y2+vQ+9GvwlktuMhcOAWd\/j4tcuBRSsDdu2uP78NS58y60Xa45\/H+R3ubFnlbQTXqYZhnb4WiCV52OMD3P86O3GH66Z+GVIXKDgKDrAEDctuaAEOR9zucgF\/fLefxoqKm4rAfygIFzZ630npjP49ZjgvkTbsUxn\/G4KT8niBqjSl\/OnjmtRolqEdWXRFgRi48Ff9Qipz2jZkgDJwYyz+I0AZLpYYMB8r491ymm5WyrWHWhumEL1TKc3GZvMOxx6GUPzo22\/SGAGDDaSK+zeGLUR2i0j0I78oGmcFxuegHs5R0UwYS\/HE6gwggQiMIIDCqADAgECAggB3rzEOW2gEDANBgkqhkiG9w0BAQUFADBiMQswCQYDVQQGEwJVUzETMBEGA1UEChMKQXBwbGUgSW5jLjEmMCQGA1UECxMdQXBwbGUgQ2VydGlmaWNhdGlvbiBBdXRob3JpdHkxFjAUBgNVBAMTDUFwcGxlIFJvb3QgQ0EwHhcNMTMwMjA3MjE0ODQ3WhcNMjMwMjA3MjE0ODQ3WjCBljELMAkGA1UEBhMCVVMxEzARBgNVBAoMCkFwcGxlIEluYy4xLDAqBgNVBAsMI0FwcGxlIFdvcmxkd2lkZSBEZXZlbG9wZXIgUmVsYXRpb25zMUQwQgYDVQQDDDtBcHBsZSBXb3JsZHdpZGUgRGV2ZWxvcGVyIFJlbGF0aW9ucyBDZXJ0aWZpY2F0aW9uIEF1dGhvcml0eTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMo4VKbLVqrIJDlI6Yzu7F+4fyaRvDRTes58Y4Bhd2RepQcjtjn+UC0VVlhwLX7EbsFKhT4v8N6EGqFXya97GP9q+hUSSRUIGayq2yoy7ZZjaFIVPYyK7L9rGJXgA6wBfZcFZ84OhZU3au0Jtq5nzVFkn8Zc0bxXbmc1gHY2pIeBbjiP2CsVTnsl2Fq\/ToPBjdKT1RpxtWCcnTNOVfkSWAyGuBYNweV3RY1QSLorLeSUheHoxJ3GaKWwo\/xnfnC6AllLd0KRObn1zeFM78A7SIym5SFd\/Wpqu6cWNWDS5q3zRinJ6MOL6XnAamFnFbLw\/eVovGJfbs+Z3e8bY\/6SZasCAwEAAaOBpjCBozAdBgNVHQ4EFgQUiCcXCam2GGCL7Ou69kdZxVJUo7cwDwYDVR0TAQH\/BAUwAwEB\/zAfBgNVHSMEGDAWgBQr0GlHlHYJ\/vRrjS5ApvdHTX8IXjAuBgNVHR8EJzAlMCOgIaAfhh1odHRwOi8vY3JsLmFwcGxlLmNvbS9yb290LmNybDAOBgNVHQ8BAf8EBAMCAYYwEAYKKoZIhvdjZAYCAQQCBQAwDQYJKoZIhvcNAQEFBQADggEBAE\/P71m+LPWybC+P7hOHMugFNahui33JaQy52Re8dyzUZ+L9mm06WVzfgwG9sq4qYXKxr83DRTCPo4MNzh1HtPGTiqN0m6TDmHKHOz6vRQuSVLkyu5AYU2sKThC22R1QbCGAColOV4xrWzw9pv3e9w0jHQtKJoc\/upGSTKQZEhltV\/V6WId7aIrkhoxK6+JJFKql3VUAqa67SzCu4aCxvCmA5gl35b40ogHKf9ziCuY7uLvsumKV8wVjQYLNDzsdTJWk26v5yZXpT+RN5yaZgem8+bQp0gF6ZuEujPYhisX4eOGBrr\/TkJ2prfOv\/TgalmcwHFGlXOxxioK0bA8MFR8wggS7MIIDo6ADAgECAgECMA0GCSqGSIb3DQEBBQUAMGIxCzAJBgNVBAYTAlVTMRMwEQYDVQQKEwpBcHBsZSBJbmMuMSYwJAYDVQQLEx1BcHBsZSBDZXJ0aWZpY2F0aW9uIEF1dGhvcml0eTEWMBQGA1UEAxMNQXBwbGUgUm9vdCBDQTAeFw0wNjA0MjUyMTQwMzZaFw0zNTAyMDkyMTQwMzZaMGIxCzAJBgNVBAYTAlVTMRMwEQYDVQQKEwpBcHBsZSBJbmMuMSYwJAYDVQQLEx1BcHBsZSBDZXJ0aWZpY2F0aW9uIEF1dGhvcml0eTEWMBQGA1UEAxMNQXBwbGUgUm9vdCBDQTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAOSRqQkfkdseR1DrBe1eeYQt6zaiV0xV7IsZid75S2z1B6siMALoGD74UAnTf0GomPnRymacJGsR0KO75Bsqwx+VnnoMpEeLW9QWNzPLxA9NzhRp0ckZcvVdDtV\/X5vyJQO6VY9NXQ3xZDUjFUsVWR2zlPf2nJ7PULrBWFBnjwi0IPfLrCwgb3C2PwEwjLdDzw+dPfMrSSgayP7OtbkO2V4c1ss9tTqt9A8OAJILsSEWLnTVPA3bYharo3GSR1NVwa8vQbP4++NwzeajTEV+H0xrUJZBicR0YgsQg0GHM4qBsTBY7FoEMoxos48d3mVz\/2deZbxJ2HafMxRloXeUyS0CAwEAAaOCAXowggF2MA4GA1UdDwEB\/wQEAwIBBjAPBgNVHRMBAf8EBTADAQH\/MB0GA1UdDgQWBBQr0GlHlHYJ\/vRrjS5ApvdHTX8IXjAfBgNVHSMEGDAWgBQr0GlHlHYJ\/vRrjS5ApvdHTX8IXjCCAREGA1UdIASCAQgwggEEMIIBAAYJKoZIhvdjZAUBMIHyMCoGCCsGAQUFBwIBFh5odHRwczovL3d3dy5hcHBsZS5jb20vYXBwbGVjYS8wgcMGCCsGAQUFBwICMIG2GoGzUmVsaWFuY2Ugb24gdGhpcyBjZXJ0aWZpY2F0ZSBieSBhbnkgcGFydHkgYXNzdW1lcyBhY2NlcHRhbmNlIG9mIHRoZSB0aGVuIGFwcGxpY2FibGUgc3RhbmRhcmQgdGVybXMgYW5kIGNvbmRpdGlvbnMgb2YgdXNlLCBjZXJ0aWZpY2F0ZSBwb2xpY3kgYW5kIGNlcnRpZmljYXRpb24gcHJhY3RpY2Ugc3RhdGVtZW50cy4wDQYJKoZIhvcNAQEFBQADggEBAFw2mUwteLftjJvc83eb8nbSdzBPwR+Fg4UbmT1HN\/Kpm0COLNSxkBLYvvRzm+7SZA\/LeU802KI++Xj\/a8gH7H05g4tTINM4xLG\/mk8Ka\/8r\/FmnBQl8F0BWER5007eLIztHo9VvJOLr0bdw3w9F4SfK8W147ee1Fxeo3H4iNcol1dkP1mvUoiQjEfehrI9zgWDGG1sJL5Ky+ERI8GA4nhX1PSZnIIozavcNgs\/e66Mv+VNqW2TAYzN39zoHLFbr2g8hDtq6cxlPtdk2f8GHVdmnmbkyQvvY1XGefqFStxu9k0IkEirHDx22TZxeY8hLgBdQqorV2uT80AkHN7B1dSExggHLMIIBxwIBATCBozCBljELMAkGA1UEBhMCVVMxEzARBgNVBAoMCkFwcGxlIEluYy4xLDAqBgNVBAsMI0FwcGxlIFdvcmxkd2lkZSBEZXZlbG9wZXIgUmVsYXRpb25zMUQwQgYDVQQDDDtBcHBsZSBXb3JsZHdpZGUgRGV2ZWxvcGVyIFJlbGF0aW9ucyBDZXJ0aWZpY2F0aW9uIEF1dGhvcml0eQIIDutXh+eeCY0wCQYFKw4DAhoFADANBgkqhkiG9w0BAQEFAASCAQAgUodXQ3iOSt3DC67wAqVHsTKal1GJTOIR5tm7E1txw37Q3sc9sdzfYQ8aamfheDrxiQFD5tD6d4EdA0zERfiTe9H50RqhlM1KJNOzx2UnZcfNXcaPucvuC9pMQPduh5aRMyFezj1qUK1ngTv5uYUsqql+qCZKx5SyfjZvw0RengU+7SYInO6lYUJzQEdMbPJdP+XlyvBqoEU\/Q5Wkzs+epyO5mO4jXCRJVnXiamZDlLSeg+vf47HvpXesYTltfXiazORnBQfwRE\/mDru\/tRpR7WAiAfHr0gAJ8vWxNPBi18adYWEGkOpGCYpmFw2bpYiC\/Kd6d\/+vuKLC8ctDbrbv"
		self.fa_token = None
		self.fa_free_no_crop = (
			'smile',
			'smile_2',
			'old',
			'young',
			'hot'
		)
		# self.fa_ua = "FaceApp/3.1.0 (iPhone X; iPhone10,6; iOS Version 12.0 (Build 16A366); Scale/3.0)"
		# self.fa_itunes = r"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"
		# self.fa_headers = None
		# self.fa_api = "https://phv3f.faceapp.io/api/v3.1/photos"
	# 	self.fa_task = bot.loop.create_task(self.set_faceapp_token())


	# def cog_unload(self):
	# 	self.fa_task.cancel()

	@commands.command()
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def badmeme(self, ctx):
		"""returns bad meme (shit api)"""
		try:
			load = await self.imgur_client.gallery_search(
				'meme', advanced=None, sort='viral', window='all', page=0
			)
		except:
			await ctx.send('\N{WARNING SIGN} Imgur API Failed.')
		else:
			rand = random.choice(load[:10])
			await ctx.send(rand.link)


	@commands.command(aliases=['imagemagic', 'imagemagick', 'magic', 'magick', 'cas', 'liquid'])
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def magik(self, ctx, *urls:str):
		"""Apply magik to Image(s)\n .magik image_url or .magik image_url image_url_2"""
		try:
			x = None
			get_images = await self.get_images(ctx, urls=urls, limit=2, scale=5)
			if not get_images:
				return
			img_urls, scale, scale_msg = get_images
			x = await ctx.send("ok, processing")
			final = await self.generic_api(ctx.command.name, urls=', '.join(img_urls), scale=scale or 0)
			await ctx.send(file=final, filename='magik.png', content=scale_msg)
		finally:
			if x:
				await ctx.delete(x, error=False)


	@commands.command(aliases=['gmagick'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gmagik(self, ctx, *, url:str=None):
		try:
			x = await ctx.send("ok, processing (this might take a while)")
			get_images = await self.get_images(ctx, urls=url, limit=1, gif=True, msg=False)
			if not get_images:
				get_images = await self.get_images(ctx, urls=url, limit=1)
				if get_images:
					url = get_images[0]
					final = await self.generic_api('gmagik2', url)
					await ctx.send(file=final, filename='gmagik.gif')
				else:
					ctx.command.reset_cooldown(ctx)
			else:
				url = get_images[0]
				final = await self.generic_api(ctx.command.name, url, user=ctx.author.id)
				await ctx.send(file=final, filename='gmagik.gif')
		finally:
			await ctx.delete(x, error=False)


	@commands.command(aliases=['gmagick2'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gmagik2(self, ctx, *, url:str=None):
		"""Image version of gmagik"""
		try:
			x = await ctx.send("ok, processing (this might take a while)")
			get_images = await self.get_images(ctx, urls=url, limit=1)
			if not get_images:
				return
			final = await self.generic_api('gmagik2', get_images[0], loop=True)
			await ctx.send(file=final, filename='gmagik.gif')
		finally:
			await ctx.delete(x, error=False)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def triggered(self, ctx, *, url:str=None):
		"""Generate a Triggered Gif for a User or Image"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url)
		await ctx.send(file=final, filename='triggered.gif')


	async def do_triggered(self, ctx, url, t_path):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		final = await self.generic_api('triggered2', url, t_path=t_path)
		await ctx.send(file=final, filename=f'{t_path}.png')

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def triggered2(self, ctx, *, url:str=None):
		await self.do_triggered(ctx, url, 'triggered.png')

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def triggered3(self, ctx, *, url:str=None):
		await self.do_triggered(ctx, url, 'triggered2.png')


	@commands.command(aliases=['aes', 'aesthetic'])
	async def aesthetics(self, ctx, *, text:commands.clean_content):
		"""Returns inputed text in aesthetics"""
		final = ""
		pre = ' '.join(text)
		for char in pre:
			if not ord(char) in range(33, 127):
				final += char
				continue
			final += chr(ord(char) + 65248)
		try:
			await ctx.delete(ctx.message)
		except:
			pass
		await self.truncate(ctx.channel, final)


	@commands.command(aliases=['expand'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def ascii(self, ctx, *, text:commands.clean_content):
		"""Convert text into ASCII"""
		if len(text) > 1000:
			return await ctx.send("2 long asshole")
		if text == 'donger' or text == 'dong':
			text = "8====D"
		r = await self.generic_api(ctx.command.name, text=text, json=True)
		if r is False:
			return await ctx.send('\N{NO ENTRY} go away with your invalid characters.')
		final, txt = r.values()
		b = BytesIO(eval(final))
		b.seek(0)
		msg = f"```fix\n{txt}```" if len(txt) <= 600 else None
		await ctx.send(file=b, filename='ascii.png', content=msg)


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def iascii(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=2)
		if not get_images:
			return
		x = await ctx.send("ok, processing")
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url)
			await ctx.send(file=final, filename='iascii.png')
		await ctx.delete(x)


	@commands.command()
	@commands.cooldown(1, 10, commands.BucketType.guild)
	async def gascii(self, ctx, *, url:str=None):
		"""Gif to ASCII"""
		get_images = await self.get_images(ctx, urls=url, gif=True, limit=1)
		if not get_images:
			return
		url = get_images[0]
		x = await ctx.send("ok, processing")
		final = await self.generic_api(ctx.command.name, url, user=ctx.author.id)
		await ctx.delete(x)
		await ctx.send(file=final, filename='gascii.gif')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def rip(self, ctx, name:commands.clean_content=None, *, text:commands.clean_content=None):
		if name is None:
			name = ctx.author.name
		if len(ctx.message.mentions) >= 1:
			name = ctx.message.mentions[0].name
		if text:
			if len(text) > 22:
				one = text[:22]
				two = text[22:]
				url = "http://www.tombstonebuilder.com/generate.php?top1=R.I.P&top3={0}&top4={1}&top5={2}".format(name, one, two)
			else:
				url = "http://www.tombstonebuilder.com/generate.php?top1=R.I.P&top3={0}&top4={1}".format(name, text)
		else:
			if name[-1].lower() != 's':
				name += "'s"
			url = "http://www.tombstonebuilder.com/generate.php?top1=R.I.P&top3={0}&top4=Hopes and Dreams".format(name)
		b = await self.bytes_download(url.replace(' ', '%20').replace('\n', '%0A'), proxy=True)
		await ctx.send(file=b, filename='rip.png')


	@commands.command()
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def urban(self, ctx, *, word:str=None):
		urb = await urbandict.define(word)
		if not urb or "There aren't any definitions" in urb[0]['def']:
			return await ctx.send(":no_mouth: `No definition found.`")
		e = discord.Embed()
		e.title = word
		e.color = 0x738bd7
		e.description = urb[0]['def'][:2048]
		for x in urb[:3]:
			ex = x['example']
			if ex:
				e.add_field(name='Example', value=ex[:1024], inline=True)
		await ctx.send(embed=e)


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def imgur(self, ctx, *, text:str=None):
		try:
			if text is None:
				load = await self.imgur_client.gallery_random(page=0)
			else:
				load = await self.imgur_client.gallery_search(text, advanced=None, sort='viral', window='all', page=0)
		except:
			await ctx.send('\N{WARNING SIGN} Imgur API Failed.')
		else:
			if not load:
				return await ctx.send('\N{WARNING SIGN} `No results found on` <https://imgur.com>')
			rand = random.choice(load)
			try:
				if 'image/' in rand.type:
					await ctx.send('{0}'.format(rand.link))
			except AttributeError:
				if rand.title:
					title = '**'+rand.title+'**\n'
				else:
					title = ''
				if rand.description:
					desc = '`'+rand.description+'`\n'
				else:
					desc = ''
				await ctx.send('{0}{1}{2}'.format(title, desc, rand.link))


	@commands.command(aliases=['gif'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def giphy(self, ctx, *, text:str=None):
		if not text:
			api = 'http://api.giphy.com/v1/gifs/random?&api_key=dc6zaTOxFJmzC'
		else:
			api = 'http://api.giphy.com/v1/gifs/search?q={0}&api_key=dc6zaTOxFJmzC'.format(quote(text))
		load = await self.get_json(api)
		if 'data' not in load or not load['data']:
			await ctx.send('\N{WARNING SIGN} `No results found on` <https://giphy.com>')
		else:
			rand = False
			try:
				gif = random.choice(load['data'])
			except:
				gif = load['data']
				rand = True
			url = gif['url']
			if rand:
				url = gif['image_url']
			else:
				url = gif['images']['fixed_height']['url']
			await ctx.send(url)


	@commands.command(aliases=['w2x', 'waifu2x', 'enlarge', 'upscale'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def resize(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, scale=10, limit=1)
		if not get_images:
			return
		url = get_images[0][0]
		size = get_images[1]
		size = 2 if not size else int(size)
		scale_msg = get_images[2]
		if not scale_msg:
			scale_msg = ''
		else:
			scale_msg = '\n'+scale_msg
		x = await ctx.send("ok, resizing `{0}` by `{1}`".format(url, size))
		final = await self.generic_api(ctx.command.name, url, size=size)
		await ctx.send(file=final, filename='enlarge.png', content='Visit image link for accurate resize visual.'+scale_msg if size > 3 else scale_msg if scale_msg != '' else None)
		await ctx.delete(x)


	def split_text(self, text):
		result = (text, '')
		if len(text) >= 3 and ' ' in text[1:-1]:
			space_indices = [i for i in range(len(text)) if text[i] == ' ']
			space_proximities = [abs(i - len(text) // 2) for i in space_indices]
			for i, j in zip(space_proximities, space_indices):
				if i == min(space_proximities):
					result = (text[:j], text[j + 1:])
					break
		return result

	@commands.command()
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def meme(self, ctx, url:str, *, txt:str):
		"""You can split top and bottom text using a | divider."""
		get_images = await self.get_images(ctx, urls=url, msg=False)
		if not get_images:
			get_images = await self.get_images(ctx)
			if not get_images:
				return
			txt = url + " " + txt
		if '|' in txt:
			split = txt.split('|')
			line1 = split[0]
			if len(split) > 1:
				line2 = split[1]
		else:
			line1, line2 = self.split_text(txt)
		rep = (["-","--"], ["_", "__"], ["?", "~q"], ["%", "~p"], [" ", "%20"], ["''", "\""], ["/","~s"])
		for s in rep:
			line1 = line1.replace(s[0], s[1])
			line2 = line2.replace(s[0], s[1])
		link = f"https://memegen.link/custom/{line1 if line1 != '' else ' '}/{line2}.jpg?alt={get_images[0]}&watermark=none"
		b = await self.bytes_download(link, headers={'referer': 'https://memegen.link/custom'})
		await ctx.send(file=b, filename='meme.png')


	@commands.command(aliases=['r'])
	@commands.cooldown(1, 1, commands.BucketType.guild)
	async def reverse(self, ctx, *, text:str):
		"""Reverse Text\n.reverse <text>"""
		await ctx.send(text[::-1], replace_mentions=True, zero_width=True)


	async def get_twitch_emote(self, emote:str):
		url = f"https://twitchemotes.com/search?query={quote(emote[:20])}"
		body = await self.proxy_request('get', url, text=True, timeout=10)
		if body:
			root = etree.fromstring(body, etree.HTMLParser(collect_ids=False))
			emotes = root.findall('.//img[@class="emote"]')
			for e in emotes:
				if e.get('data-regex') == emote:
					return f"{e.get('src')[:-4]}/3.0"

	@commands.command(aliases=['e', 'em', 'hugemoji', 'hugeemoji'])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def emoji(self, ctx, *ems:str):
		"""Returns a large emoji image"""
		if not ems:
			return await ctx.send('\N{NO ENTRY} Please input emotes to enlargen.')

		ems = list(ems)
		size = 1024
		if len(ems) > 1:
			for e in ems:
				if e.isdigit():
					s = int(e)
					if len(e) < 5 and 9 < s < 2048:
						size = s
						ems.remove(e)
						break

		path = steam = epath = None
		fmt = "svg"

		for em in ems:
			if em == 'emojione' or em == 'one':
				epath = 'emojione'
			elif em == 'apple' or em.lower() == 'ios':
				epath = 'apple_emoji'
				fmt = 'png'
			elif em == 'steam':
				steam = True
			if epath or steam:
				ems.remove(em)
				break

		if epath is None:
			epath = "twemoji"

		list_imgs = []
		for em in ems:
			if em == ' ' or em == '​':
				continue

			gif = False
			path = await self.emoji_path(
				em, path=epath,
				fmt=fmt, verify=True
			)

			# weird variation selector
			if not path and len(em) > 1 and em[1] == "\ufe0f":
				path = await self.emoji_path(
					em[:1], path=epath,
					fmt=fmt, verify=True
				)

			if not path:
				match = self.emote_regex.match(em)
				if match:
					gif = bool(match.group(1))
					emote = f"https://cdn.discordapp.com/emojis/{match.group(2)}.{'gif' if gif else 'png'}"
					path = await self.bytes_download(emote)

				if not path and steam:
					url = f"https://steamcommunity-a.akamaihd.net/economy/emoticon/{em.lower()}"
					path = await self.bytes_download(url)

				if not path and em in self.emojis:
					path = await self.emoji_path(self.emojis[em])

				if not path and 1 < len(em) <= 20:
					url = await self.get_twitch_emote(em)
					if url:
						path = await self.bytes_download(url)

			if path:
				list_imgs.append(path)
			# else:
			# 	alps = [x.lower() for x in em if x.isdigit() or x in alphabet]
			# 	for w in alps[:24]:
			# 		path = self.emoji_path(self.regional_map[w])
			# 		list_imgs.append(path)

		if not list_imgs or (len(list_imgs) == 1 and list_imgs[0] is False):
			return await ctx.send("\N{WARNING SIGN} `Emoji Invalid/Not Found`")

		svgs = [(i, p) for i, p in enumerate(list_imgs)
						if isinstance(p, str) and p.endswith('.svg')]
		if svgs:
			pngs = await self.png_svg([x[1] for x in svgs], size)
			if not pngs:
				return await ctx.send(
					"\N{WARNING SIGN} `API failed to process >= 1 emoji, try again."
				)

			for i, s in enumerate(svgs):
				idx = s[0]
				list_imgs[idx] = pngs[i]

		if len(list_imgs) > 1:
			list_imgs = [b64encode(b.read()).decode() for b in list_imgs]
			b = await self.merge_images(list_imgs)
		else:
			img = list_imgs[0]
			if isinstance(img, str):
				# Remote Emoji
				if img.startswith("http"):
					b = await self.bytes_download(img)
				else:
					# Local API Emoji
					b = await self.generic_api("get_file", path=img)
			else:
				b = img

		await ctx.send(file=b, filename='emote.gif' if gif and len(list_imgs) == 1 else 'emote.png')


	@commands.command(aliases=['steamemoji', 'steame', 'semoji'])
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def se(self, ctx, em:str):
		"""Returns a steam emoji image"""
		try:
			em = em.lower()
			desc = None
			if em == ':b1:' or em == 'b1':
				b = self.files_path('b1.png')
			else:
				txt = await self.get_text(f"https://steamcommunity-a.akamaihd.net/economy/emoticonhover/{em}")
				assert txt
				root = etree.fromstring(txt, etree.HTMLParser(collect_ids=False))
				base = root.find('.//img[@class="emoticon_large"]')
				assert base is not None
				b = BytesIO(b64decode(base.attrib['src'][22:]))
				desc = '**{0}**'.format(root.find('.//div[@class="emoticon_hover_desc"]').text)
			await ctx.send(file=b, filename='steam.png', content=desc)
		except:
			await ctx.send(
				"\N{WARNING SIGN} `Emoticon Not Found/Invalid`\nRemember to do :steam_emoticon: (optional ':')."
			)


	@commands.command()
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def b1(self, ctx):
		"""cool"""
		await ctx.send(file=self.files_path('b1.png'))


	@commands.group(invoke_without_command=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def merge(self, ctx, *urls:str):
		"""Merge/Combine Photos"""
		get_images = await self.get_images(ctx, urls=urls, limit=10)
		if get_images and len(get_images) == 1:
			return await ctx.send('You gonna merge one image?')
		elif not get_images:
			return
		final = await self.generic_api(ctx.command.name, urls=json.dumps(get_images), vertical=0)
		await ctx.send(file=final, filename='merge.png')


	@merge.command(name='vertical')
	async def merge_vertical(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=10)
		if get_images and len(get_images) == 1:
			return await ctx.send('You gonna merge one image?')
		elif not get_images:
			return
		final = await self.generic_api('merge', urls=json.dumps(get_images), vertical=1)
		await ctx.send(file=final, filename='merge_vertical.png')


	@commands.command(aliases=['text2img', 'texttoimage', 'text2image'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def tti(self, ctx, *, txt:str):
		api = 'http://api.img4me.com/?font=arial&fcolor=FFFFFF&size=35&type=png&text={0}'.format(quote(txt))
		r = await self.get_text(api)
		b = await self.bytes_download(r)
		await ctx.send(file=b, filename='tti.png')


	@commands.command(aliases=['comicsans'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def sans(self, ctx, *, txt:str):
		api = 'http://api.img4me.com/?font=sans&fcolor=000000&size=35&type=png&text={0}'.format(quote(txt))
		r = await self.get_text(api)
		b = await self.bytes_download(r)
		await ctx.send(file=b, filename='tti.png')


	@commands.command(aliases=['needsmorejpeg', 'jpegify', 'magik2'])
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def jpeg(self, ctx, *urls:str):
		"""Add more JPEG to an Image\nNeeds More JPEG!"""
		get_images = await self.get_images(ctx, urls=urls, scale=100)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, quality=scale or 1)
			await ctx.send(content=scale_msg, file=final, filename='needsmorejpeg.jpg')


	@commands.command(aliases=['gifjpeg'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gjpeg(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, gif=True, scale=100, limit=1)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url, scale=scale or 1)
		await ctx.send(file=final, filename='gjpeg.gif', content=scale_msg)


	@commands.command(aliases=['vaporwave', 'vape', 'vapewave'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def vw(self, ctx, url:str=None, *, txt:str=None):
		"""Vaporwave an image!"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		if txt is None:
			txt = "vapor wave"
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, txt=txt)
			await ctx.send(file=final, filename='vapewave.png')


	@commands.command(aliases=['achievement', 'ach'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def mc(self, ctx, *, txt:str):
		"""Generate a Minecraft Achievement"""
		api = f"https://www.minecraftskinstealer.com/achievement/a.php?i=1&h=Achievement+Get!&t={txt}"
		b = await self.bytes_download(api)
		await ctx.send(file=b, filename='achievement.png')


	async def do_cowsay(self, ctx, txt, animal=None):
		final = await self.generic_api('cowsay', txt=txt, animal=animal or 'default', raw=True)
		msg = f"```\n{final[:1992]}```" if final else "\N{WARNING SIGN} Cowsay input invalid."
		await ctx.send(msg)

	@commands.group(aliases=['cow'])
	async def cowsay(self, ctx, *, txt:str):
		"""Aliases can be accesed by removing "say"."""
		await self.do_cowsay(ctx, txt)

	@commands.command(aliases=['pony'])
	async def ponysay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'unipony-smaller')

	@commands.command(aliases=['flamingsheep'])
	async def flamingsheepsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'flaming-sheep')

	@commands.command(aliases=['apt'])
	async def aptsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'apt')

	@commands.command(aliases=['dino'])
	async def dinosay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'stegosaurus')

	@commands.command(aliases=['moofasa'])
	async def moofasasay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'moofasa')

	@commands.command(aliases=['sodomizedsheep', 'sodomized'])
	async def sodomizedsheepsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'sodomized')

	@commands.command(aliases=['bong'])
	async def bongsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'bong')

	@commands.command(aliases=['beavis'])
	async def beavissay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'beavis.zen')

	@commands.command(aliases=['tux'])
	async def tuxsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'tux')

	@commands.command(aliases=['duck'])
	async def ducksay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'duck')

	@commands.command(aliases=['elephant'])
	async def elephantsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'elephant')

	@commands.command(aliases=['sheep'])
	async def sheepsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'sheep')

	@commands.command(aliases=['mech'])
	async def mechsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'mech-and-cow')

	@commands.command()
	async def eyessay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'eyes')

	@commands.command(aliases=['milk'])
	async def milksay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'milk')

	@commands.command(aliases=['moose'])
	async def moosesay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'moose')

	@commands.command(aliases=['mutilated'])
	async def mutilatedsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'mutilated')

	@commands.command(aliases=['cock'])
	async def cocksay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'cock')

	@commands.command(aliases=['headinass', 'headinasssay'])
	async def headinsay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'head-in')

	@commands.command(aliases=['cheese'])
	async def cheesesay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'cheese')

	@commands.command(aliases=['gopher', 'golang', 'gosay'])
	async def gophersay(self, ctx, *, txt:str):
		await self.do_cowsay(ctx, txt, 'gopher')


	async def process_eyes(self, ctx, url, path, resize_amount=130, **kwargs):
		get_images = await self.get_images(ctx, urls=url, limit=1, scale=300)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		url = get_images[0]
		flipped = kwargs.pop('flipped', False)

		r = await self.gcv_request(url, "FACE_DETECTION")
		if not r:
			return await ctx.send("\N{NO ENTRY} `Google Vision API returned an error.`")
		elif not r['responses'][0]:
			return await ctx.send("\N{NO ENTRY} `Face not detected.`")

		faces = []
		for f in r['responses'][0]['faceAnnotations']:
			lm = f['landmarks']
			left_eye = lm[0]['position']
			right_eye = lm[1]['position']

			bp = f['fdBoundingPoly']['vertices']
			last_bp = bp[-1]
			first_bp = bp[0]
			if all("y" in x for x in (last_bp, first_bp)):
				height = last_bp['y'] - first_bp['y']
			else:
				height = max(x['y'] for x in bp if "y" in x)

			faces.append({
				'eyes': [
					{
						'x': left_eye['x'],
						'y': left_eye['y']
					},
					{
						'x': right_eye['x'],
						'y': right_eye['y']
					},
				],
				'roll': f['rollAngle'],
				'height': height
			})

		# place the eyes
		final = await self.generic_api(
			'eyes', url, path=path, faces=json.dumps(faces),
			resize_amount=scale or resize_amount, flipped=1 if flipped else 0
		)
		await ctx.send(content=scale_msg, file=final, filename="eyes.png")

	@commands.group(aliases=['eye'], invoke_without_command=True)
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes(self, ctx, *urls:str):
		"""Alias for the eye name is also the command number (e.g. ".eyes 1" instead of ".eyes spongebob")."""
		await self.process_eyes(ctx, urls, 'eye.png')

	@eyes.command(name='spongebob', aliases=['1', 'sponge'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_spongebob(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'spongebob_eye.png')

	@eyes.command(name='big', aliases=['2'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_big(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'big_eye.png', resize_amount=110)

	@eyes.command(name='small', aliases=['3'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_small(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'small_eye.png', resize_amount=110)

	@eyes.command(name='money', aliases=['4'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_money(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'money_eye.png')

	@eyes.command(name='blood', aliases=['5'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_blood(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'bloodshot_eye.png', resize_amount=200)

	@eyes.command(name='horror', aliases=['6'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_horror(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'red_eye.png', resize_amount=200)

	@eyes.command(name='illuminati', aliases=['7', 'triangle'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_illuminati(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'illuminati_eye.png', resize_amount=150)

	@eyes.command(name='googly', aliases=['8', 'googlyeye'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_googly(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'googly_eye.png', resize_amount=200)

	@eyes.command(name='flip', aliases=['9', 'flipped', 'reverse'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_flip(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'eye.png', flipped=True)

	@eyes.command(name='center', aliases=['10'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_center(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'one_eye_center.png')

	@eyes.command(name='red', aliases=['11', 'flare'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_red(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'flare_red.png', resize_amount=37)

	@eyes.command(name='blue', aliases=['12'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_blue(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'flare_blue.png', resize_amount=37)

	@eyes.command(name='green', aliases=['13'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_green(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'flare_green.png', resize_amount=37)

	@eyes.command(name='yellow', aliases=['14'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_yellow(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'flare_yellow.png', resize_amount=37)

	@eyes.command(name='pink', aliases=['15'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_pink(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'flare_pink.png', resize_amount=37)

	@eyes.command(name='white', aliases=['16'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_white(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'flare_white.png', resize_amount=37)

	@eyes.command(name='black', aliases=['17'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_black(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'flare_black.png', resize_amount=37)

	@eyes.command(name='spinner', aliases=['18', 'fidget'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def eyes_spinner(self, ctx, *urls:str):
		await self.process_eyes(ctx, urls, 'spinner.png', resize_amount=25)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def identify(self, ctx, *, url:str=None):
		"""Identify an image/gif using Microsofts Captionbot API"""
		get_images = await self.get_images(ctx, urls=url)
		if not get_images:
			return
		url = get_images[0]
		payload = {
			'Type': 'CaptionRequest',
			'Content': url
		}
		try:
			msg = await self.post_data('https://captionbot.azurewebsites.net/api/messages?language=en-US',
																 	payload, text=True)
			assert msg
			await ctx.send(f"`{msg}`")
		except AssertionError:
			await ctx.send('\N{WARNING SIGN} `Microsoft CaptionBot API Failed.`')


	@commands.command()
	@commands.guild_only()
	@commands.cooldown(1, 30, commands.BucketType.guild)
	@checks.admin_or_perm(manage_guild=True)
	async def ms(self, ctx, amount:int, user:discord.User, channel:discord.TextChannel=None):
		if amount > 100 and not await self.bot.is_owner(ctx.author):
			return await ctx.send("2 many mentions asshole")
		elif await self.bot.is_owner(user):
			return await ctx.send('fuck off')
		try:
			await ctx.delete(ctx.message)
		except:
			pass
		if not channel:
			channels_readable = []
			for c in ctx.guild.channels:
				if not isinstance(c, discord.TextChannel):
					continue
				perms = c.permissions_for(user)
				if perms.send_messages and c.permissions_for(ctx.me).send_messages:
					channels_readable.append(c)
		count = 0
		mention = f'{user.mention}'
		for _ in range(amount):
			if not channel:
				for c in channels_readable:
					if count == amount:
						break
					await c.send(mention, delete_after=0, replace_mentions=False)
					count += 1
			else:
				await channel.send(mention, delete_after=0, replace_mentions=False)
		await ctx.send('done', delete_after=5)


	async def do_tts(self, ctx, text, voice="en-US_AllisonV3"):
		url = f'https://text-to-speech-demo.ng.bluemix.net/api/v3/synthesize?voice={voice}Voice&download=true&accept=audio%2Fmp3' \
					f'&text={quote(text)}'
		b = await self.bytes_download(url, timeout=20)
		await ctx.send(file=b, filename="tts.mp3")

	@commands.group(invoke_without_command=True, aliases=['texttospeech', 'text2speech', 't2s'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def tts(self, ctx, *, text:commands.clean_content):
		"""Text to speech"""
		await self.do_tts(ctx, text)

	@tts.command(name='lisa')
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_lisa(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "en-US_LisaV3")

	@tts.command(name='michael')
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_michael(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "en-US_MichaelV3")

	@tts.command(name='brazil', aliases=['br', 'brasil', 'huehue'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_brazil(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "pt-BR_Isabela")

	@tts.command(name='uk', aliases=['gb', 'british'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_uk(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "en-GB_Kate")

	@tts.command(name='spanish', aliases=['es'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_spanish(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "es-ES_Enrique")

	@tts.command(name='french', aliases=['fr'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_french(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "fr-FR_Renee")

	@tts.command(name='german', aliases=['de', 'nazi'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_german(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "de-DE_Dieter")

	@tts.command(name='italian', aliases=['it'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_italian(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "it-IT_Francesca")

	@tts.command(name='japanese', aliases=['jp'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def tts_japanese(self, ctx, *, text:commands.clean_content):
		await self.do_tts(ctx, text, "ja-JP_Emi")


	@commands.command(aliases=['brazzer', 'br'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def brazzers(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='brazzers.png')


	@commands.command(aliases=['jpglitch'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def glitch(self, ctx, url:str=None, iterations:int=None, amount:int=None, seed:int=None):
		get_images = await self.get_images(ctx, urls=url, msg=False)
		gif = False
		if not get_images:
			get_images = await self.get_images(ctx, urls=url, gif=True)
			if get_images:
				gif = True
			else:
				return
		url = get_images[0]
		if not gif:
			if iterations is None:
				iterations = random.randint(1, 30)
			if amount is None:
				amount = random.randint(1, 20)
			elif amount > 99:
				amount = 99
			if seed is None:
				seed = random.randint(1, 20)
			final = await self.generic_api(ctx.command.name, url, its=iterations, amount=amount, seed=seed)
			await ctx.send(file=final, filename='glitch.jpeg', content='Iterations: `{0}` | Amount: `{1}` | Seed: `{2}`'.format(iterations, amount, seed))
		else:
			final = await self.generic_api('gglitch', url)
			await ctx.send(file=final, filename='glitch.gif')


	@commands.command(aliases=['gg', 'glitch3', 'gglitch'])
	async def glitchgif(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='glitch.gif')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def glitch2(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='glitch2.png')


	@commands.command(aliases=['pixelsort'])
	@commands.cooldown(2, 5, commands.BucketType.user)
	async def sort(self, ctx, url:str=None, *args):
		angle = 0
		randomness = 0
		interval = 'edges'
		s_func = 'lightness'
		if args:
			for arg in args:
				if arg.isdigit() and arg != '0' and angle is 0:
					angle = int(arg)
				elif randomness is 0 and arg.isdigit():
					randomness = int(arg)
				elif interval == 'edges':
					interval = str(arg)
				else:
					s_func = str(arg)
		get_images = await self.get_images(ctx, urls=url)
		if not get_images:
			return
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url, interval=interval,
																	 s_func=s_func, angle=angle, randomness=randomness)
		await ctx.send(file=final, filename='pixelsort.png', content=
			'Interval: `{0}` | Sorting: `{1}`{2}{3}'.format(
				interval, s_func, ' | Angle: **{0}**'.format(angle) if angle != 0 else '',
				' | Randomness: **{0}**'.format(randomness) if randomness != 0 else ''
			)
		)


	@commands.command(aliases=['pixel'])
	@commands.cooldown(2, 5)
	async def pixelate(self, ctx, *urls):
		get_images = await self.get_images(ctx, urls=urls, limit=1, scale=3000)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		final = await self.generic_api(ctx.command.name, get_images[0], scale=scale or 9)
		await ctx.send(file=final, filename='pixelated.png', content=scale_msg)


	@commands.command(aliases=['gpixel'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gpixelate(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, gif=True, scale=3000, limit=1)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url, scale=scale or 9)
		await ctx.send(file=final, filename='gpixel.gif', content=scale_msg)


	async def do_retro(self, ctx, text, bcg):
		if '|' not in text:
			if len(text) >= 15:
				text = [text[i:i + 15] for i in range(0, len(text), 15)]
			else:
				split = text.split()
				if len(split) == 1:
					text = ['', split[0]]
				elif len(split) == 3 or (len(split) > 1 and len(split) <= 3):
					text = split
				else:
					text = [x for x in text]
					if len(text) == 4:
						text[2] = text[2]+text[-1]
						del text[3]
		else:
			text = text.split('|')
		payload = FormData()
		payload.add_field('current-category', 'all_effects')
		payload.add_field('bcg', bcg)
		payload.add_field('txt', '4')
		count = 1
		for s in text:
			if count > 3:
				break
			payload.add_field(f'text{count}', s.replace("'", "\'"))
			count += 1
		r = await self.proxy_request('post', 'https://photofunia.com/effects/retro-wave', data=payload, timeout=20)
		try:
			assert r
			body = await self.proxy_request('get', r.url, text=True, timeout=20)
			assert body
			match = self.photofunia_regex.search(body)
			if not match:
				await ctx.send('\N{NO ENTRY} `This text contains unsupported characters.`')
				return False
			url = match.group()
			e = discord.Embed()
			e.set_image(url=url)
			await ctx.send(embed=e)
			# b = await self.bytes_download(download_url, timeout=7)
			# return b
		except AssertionError:
			await ctx.send('\N{WARNING SIGN} `Retro API Failed.`')
			return False

	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def retro(self, ctx, *, text:commands.clean_content):
		await self.do_retro(ctx, text, '5')

	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def retro2(self, ctx, *, text:commands.clean_content):
		await self.do_retro(ctx, text, '2')

	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def retro3(self, ctx, *, text:commands.clean_content):
		await self.do_retro(ctx, text, '4')


	@commands.command(aliases=['magik3', 'mirror'])
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def waaw(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='waaw.png')


	@commands.command(aliases=['magik4', 'mirror2'])
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def haah(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='haah.png')


	@commands.command(aliases=['magik5', 'mirror3'])
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def woow(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='woow.png')


	@commands.command(aliases=['magik6', 'mirror4'])
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def hooh(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='hooh.png')


	@commands.command()
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def flip(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='flip.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def flop(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='flop.png')


	@commands.command(aliases=['inverse', 'negate'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def invert(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='invert.png')


	@commands.command(aliases=['gi'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def ginvert(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, gif=True)
		if not get_images:
			return
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url)
		await ctx.send(file=final, filename='ginvert.gif')


	@commands.command(aliases=['indicator'])
	async def regional(self, ctx, *, txt:str):
		msg = ''
		for s in txt.lower():
			if s in self.regional_map.keys():
				msg += f'\N{ZERO WIDTH SPACE}{self.regional_map[s]}​'
			elif s == ' ':
				msg += '  '
			else:
				msg += s
		await ctx.send(msg)


	@commands.command()
	@commands.cooldown(1, 10, commands.BucketType.guild)
	@checks.bot_has_perms(add_reactions=True)
	async def react(self, ctx, *, txt:str):
		msg = None
		channel = ctx.channel
		for c in ctx.message.channel_mentions:
			channel = c
			txt = txt.replace(c.mention, '')
		if ctx.guild and not channel.permissions_for(ctx.author).send_messages:
			return await ctx.send('\N{NO ENTRY} `You do not have permission to message in that channel.`')
		for s in txt.split():
			if s.isdigit():
				if len(s) >= 15:
					try:
						msg = await channel.fetch_message(int(s))
					except:
						continue
					else:
						txt = txt.replace(s, '')
						break
		if not msg:
			msg = ctx.message
		count = 0
		icount = 0
		continue_count = 0
		added = []
		indexs = {}
		_x = False
		word_emotes = ['cool', 'ok', 'ng', 'up', 'new', 'ab', 'cl', 'sos', 'id']
		for split in txt.lower().split():
			if split in word_emotes and split not in added:
				indexs[txt.lower().rindex(split)] = [len(split), self.emojis[split]]
			match = self.emote_regex.match(split)
			if match:
				if em:
					indexs[txt.lower().rindex(split)] = [len(split), split]
		for s in txt.lower():
			if len(added) == 20:
				break
			if s == ' ':
				continue
			if icount in indexs:
				i = indexs[icount]
				if i[1] in added:
					continue
				continue_count += i[0]
				await ctx.add_reaction(msg, i[1])
				added.append(i[1])
				count += 1
			else:
				if icount == 0:
					icount += 1
			if continue_count != 0:
				icount += 1
				continue_count -= 1
				continue
			em = None
			if s not in added:
				if s in self.regional_map:
					em = self.regional_map[s]
				elif s in self.emojis:
					em = self.emojis[s]
				else:
					for e in self.emojis:
						if self.emojis[e] == s:
							em = self.emojis[e]
							break
					if em is None:
						if s == '?':
							em = self.emojis['question']
						elif s == '!':
							em = self.emojis['exclamation']
						elif s == '#':
							em = self.emojis['hash']
			else:
				if s == 'a' or s == 'b' or s == 'm':
					em = self.emojis[s]
				elif s == 'c':
					em = self.emojis['copyright']
				elif s == 'r':
					em = self.emojis['registered']
				elif s == 'o':
					em = self.emojis['o2']
				elif s == 'p':
					em = self.emojis['parking']
				elif s == 'i':
					em = self.emojis['information_source']
				elif s == 'l':
					if txt.lower().count('i') <= 1:
						em = self.regional_map['i']
				elif s == 'e':
					em = self.emojis['email']
				elif s == 'm':
					em = self.emojis['scorpius']
				elif s == 'o':
					em = self.emojis['zero']
				elif s == 'x':
					if _x:
						em = self.emojis['heavy_multiplication_x']
					else:
						em = self.emojis[s]
						_x = True
			if em:
				await ctx.add_reaction(msg, em)
				added.append(s)
				count += 1
			icount += 1
		if count == 0:
			await ctx.send('\N{NO ENTRY} Invalid Text.')
		else:
			x = await ctx.send('\N{WHITE HEAVY CHECK MARK} Added `{0}` reactions.'.format(count))
			await asyncio.sleep(5)
			try:
				if msg != ctx.message:
					await ctx.delete([x, ctx.message])
				else:
					await ctx.delete(x)
			except:
				pass


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def wasted(self, ctx, *, url:str=None):
		"""GTA5 Wasted Generator"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='wasted.png')


	@commands.command(aliases=['greentext', '>'])
	@commands.cooldown(1, 2, commands.BucketType.guild)
	async def green(self, ctx, *, txt:str):
		await ctx.send('```css\n>{0}\n```'.format(txt), replace_mentions=True)


	@commands.command(aliases=['lsd', 'drugs', 'wew'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def rainbow(self, ctx, *, url:str=None):
		"""Change images color matrix multiple times into a gif"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='rainbow.gif')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def waves(self, ctx, *, url:str=None):
		"""Wave image multiple times into a gif"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api("wave", get_images[0])
		await ctx.send(file=final, filename='wave.gif')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def wall(self, ctx, *, url:str=None):
		"""Image multiplied with curved perspective or wall of text"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='wall.png')


	@commands.command(aliases=['twall'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def textwall(self, ctx, *, txt:str):
		txt = txt.replace('`', '\N{ZERO WIDTH SPACE}`')
		if len(txt) > 50:
			txt = txt[:50]
		i = 0
		msg = '\n'
		while i <= len(txt):
			msg += '\n{0} {1}'.format(txt[i:], txt[:i])
			i += 1
		await ctx.send(f'```{msg[:1994]}```')


	@commands.command(aliases=['cappend', 'layers'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def layer(self, ctx, *, url:str=None):
		"""Layers an image with its self"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='layer.png')


	@commands.command()
	@commands.cooldown(3, 5, commands.BucketType.guild)
	async def rotate(self, ctx, *urls:str):
		"""Rotate image X degrees"""
		get_images = await self.get_images(ctx, urls=urls, limit=1, scale=360)
		if not get_images:
			return
		url = get_images[0][0]
		scale = get_images[1] or random.choice([90, 180, 50, 45, 270, 120, 80])
		final = await self.generic_api(ctx.command.name, url, scale=scale)
		await ctx.send(file=final, filename='rotate.png', content='Rotated: `{0}°`'.format(scale))


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def dice(self, ctx, *, url:str=None):
		"""Dice up an image"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='dice.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def scramble(self, ctx, *, url:str=None):
		"""Scramble image"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='scramble.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def scramble2(self, ctx, *, url:str=None):
		"""Scramble image without rotation"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='scramble2.png')


	@commands.command(aliases=['multi'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def multiply(self, ctx, *, url:str=None):
		"""Shrink image multiple times on a large canvas"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='multiply.png')


	@commands.command(aliases=['multi2'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def multiply2(self, ctx, *, url:str=None):
		"""Rotate and shrink image multiple times on a large canvas"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='multiply2.png')


	@commands.command(aliases=['intensify'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def shake(self, ctx, url:str=None, *, text=None):
		"""Generate a Triggered Gif for a User or Image"""
		get_images = await self.get_images(ctx, urls=url)
		if not get_images:
			return
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, text=text)
			await ctx.send(file=final, filename='shake.gif')


	@commands.command(aliases=['360', 'grotate'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def spin(self, ctx, *, url:str=None):
		"""Make image into circular form and rotate it 360 into a gif"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='spin.gif')


	@commands.command(aliases=['randomsg', 'randmessage', 'randmsg'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def randommessage(self, ctx, user:discord.User=None):
		if user is None:
			user = ctx.author
		msgs = []
		async for m in ctx.channel.history(limit=1000, before=ctx.message):
			if m.author.id != user.id or not m.content:
				continue
			msgs.append(m.content)
		if not msgs:
			return await ctx.send('\N{WARNING SIGN} No messages found for `{0}`.'.format(user))
		msg = random.choice(msgs)
		e = discord.Embed()
		e.set_author(name=user.name, icon_url=user.avatar_url if user.avatar else user.default_avatar_url)
		e.description = msg
		e.color = self.bot.funcs.get_color()()
		e.timestamp = ctx.message.created_at
		await ctx.send(embed=e)


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def swapcolors(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='swapcolor.png')


	@commands.command(aliases=['wdt'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def whodidthis(self, ctx, *, url:str=None):
		"""Who did this meme"""
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='whodidthis.png')


	@commands.command()
	async def agar(self, ctx, *, txt:str=None):
		if not txt:
			txt = ctx.author.name
		for m in ctx.message.mentions:
			txt = txt.replace(m.mention, m.name)
		await ctx.send(do_agarify(txt))


	@commands.command(aliases=['agario'])
	async def agarify(self, ctx, *, txt:str=None):
		if not txt:
			txt = ctx.author.name
		for m in ctx.message.mentions:
			txt = txt.replace(m.mention, m.name)
		await ctx.send(do_agarify(txt, True))


	async def do_trump(self, txt, txt2="ILLEGAL"):
		adj = 'IS'
		if txt.split()[-1].lower() == 'are':
			adj = 'ARE'
			txt = txt[:-4]
		return await self.generic_api('isnowillegal', text=txt, text2=txt2, adj=adj)

	@commands.command(aliases=['illegal'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def isnowillegal(self, ctx, *, txt:commands.clean_content):
		"""Do ".illegal <text> are" to replace "IS" with "ARE" in the GIF."""
		final = await self.do_trump(txt)
		await ctx.send(file=final, filename='isnowillegal.gif')

	@commands.command(aliases=['isnowlegal'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def legal(self, ctx, *, txt:commands.clean_content):
		final = await self.do_trump(txt, "LEGAL")
		await ctx.send(file=final, filename='isnowlegal.gif')


	@commands.command(aliases=['oil'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def oilpaint(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='oilpainting.gif')


	@commands.command(aliases=['charc'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def charcoal(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='charcoal.gif')


	@commands.command()
	async def xd(self, ctx, *args:str):
		if not args:
			return await ctx.send('wtf am i gonna XD???')
		args = [x[:10] for x in args][:3]
		for _ in range(3 - len(args)):
			args.append(args[0])
		middle = 11
		premiddle = 7
		if len(args[0]) == 1:
			premiddle = 6
			middle = 10
		elif len(args[0]) == 2:
			middle = 11 - (3 - len(args[0]))
		elif len(args[0]) > 3:
			premiddle += math.floor((len(args[0]) - 3) / 3) + 1
			middle += math.floor((len(args[0]) - 3) / 2.2 + .5)
			if len(args[0]) == 10:
				premiddle += 1
		args = [x.replace('`', '\N{ZERO WIDTH SPACE}`') for x in args]
		build = f"""{args[0]}           {args[0]}    {args[1]} {args[2]}
  {args[0]}       {args[0]}      {args[1]}    {args[2]}
    {args[0]}   {args[0]}        {args[1]}     {args[2]}
{' '*premiddle}{args[0]}{' '*middle}{args[1]}     {args[2]}
    {args[0]}   {args[0]}        {args[1]}     {args[2]}
  {args[0]}       {args[0]}      {args[1]}    {args[2]}
{args[0]}           {args[0]}    {args[1]} {args[2]}"""
		await ctx.send(f'```\n{build[:1992]}\n```')


	@commands.command(aliases=['draw'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def trace(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='trace.png')


	@commands.command(aliases=['whirlpool'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def swirl(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='swirl.gif')


	@commands.command(aliases=['sts', 's2s'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def sidetoside(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='sidetoside.gif')


	@commands.command(aliases=['utd', 'u2d'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def uptodown(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='uptodown.gif')


	@commands.command(aliases=['rc'])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def recolor(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='recolor.png')


	@commands.command(aliases=['sharp'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def sharpen(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=100)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, scale=scale or 15.0)
			await ctx.send(file=final, filename='sharpen.png', content=scale_msg)


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def gay(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='gay.png')


	@commands.command(aliases=['i2o', 'io'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def inout(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=200)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, delay=scale or 40)
			await ctx.send(file=final, content=scale_msg, filename='inout.gif')


	@commands.command(aliases=['o2i', 'oi'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def outin(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=200)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, delay=scale or 40)
			await ctx.send(file=final, content=scale_msg, filename='outin.gif')


	@commands.command(aliases=['gifreverse', 'reversegif', 'greverse'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def rewind(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, gif=True, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='reverse.gif')


	@commands.command(aliases=['rewindloop'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gloop(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, gif=True, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='gloop.gif')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def blur(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=100)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		if not get_images:
			return
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, scale=scale or 2)
			await ctx.send(file=final, filename='blur.png', content=scale_msg)


	# async def get_faceapp_token(self):
	# 	api = 'https://api.faceapp.io/api/v3.0/auth/user/credentials'
	# 	payload = {
	# 		"subscription_apple": {
	# 			"receipt_data": self.fa_itunes,
	# 			"sandbox": False
	# 		}
	# 	}
	# 	did = self.gen_fa_did()
	# 	headers = {
	# 		"content-type": "application/json",
	# 		"user-agent": self.fa_ua,
	# 		"x-faceapp-deviceid": did
	# 	}
	# 	r = await self.post_data(api, json.dumps(payload), headers=headers, json=True)
	# 	if r and 'user_token' in r:
	# 		return r['user_token'], did

	# async def set_faceapp_token(self):
	# 	while not self.bot.is_closed():
	# 		token, did = await self.get_faceapp_token()
	# 		self.fa_headers = {
	# 			"user-agent": self.fa_ua,
	# 			"x-faceapp-deviceid": did,
	# 			"x-faceapp-usertoken": token,
	# 			"x-faceapp-ios": "12.0",
	# 			"x-faceapp-model": "iPhone X",
	# 			"x-faceapp-applaunched-version": "2.0.12",
	# 			"x-faceapp-applaunched": "1511713954"
	# 		}
	# 		await asyncio.sleep(120)

	# async def upload_faceapp(self, ctx, b):
	# 	data = {'file': b}
	# 	load = await self.post_data(self.fa_api, data=data, headers=self.fa_headers,
	# 															json=True, rheaders=True, timeout=25)

	# 	if not load or 'code' not in load[0]:
	# 		if load:
	# 			try:
	# 				error = load[1]['X-FaceApp-ErrorCode']
	# 			except KeyError:
	# 				msg = 'Ratelimited, try again.'
	# 			else:
	# 				if error == 'photo_bad_type':
	# 					msg = 'Invalid image provided.'
	# 				elif error == 'photo_no_faces':
	# 					msg = 'No faces detected on provided image.'
	# 				else:
	# 					msg = 'Invalid human image for filter.'
	# 		else:
	# 			msg = 'API timed out...'
	# 		await ctx.send(f'\N{WARNING SIGN} `{msg}`')
	# 		return False

	# 	return load[0]['code'], load[0]['faces_p']

	# fa_no_crop = [
	# 	"smile_2"
	# ]

	# async def faceapp_request(self, ctx, url, filter_name, editor="stylist"):
	# 	# check for init
	# 	if self.fa_headers is None:
	# 		return await ctx.send("\N{NO ENTRY} `FaceApp is initializing, try again in a bit.`")

	# 	get_images = await self.get_images(ctx, urls=url, limit=1)
	# 	if not get_images:
	# 		return
	# 	url = get_images[0]
	# 	b = await self.bytes_download(url, proxy=True)
	# 	load = await self.upload_faceapp(ctx, b)
	# 	if not load:
	# 		return
	# 	code, faces = load

	# 	fl = len(faces)
	# 	if fl > 1 :
	# 		overlay = await self.generic_api('draw_faces', url, faces=json.dumps(faces))
	# 		e = discord.Embed()
	# 		e.title = f"{fl} faces detected!"
	# 		e.description = "Please specify the face by responding with the corresponding number(s).\n" \
	# 										'e.g. "1,2,4" or "1"\n' \
	# 										"You can also respond with **all** for up to 5 faces."
	# 		e.color = discord.Color.blue()
	# 		e.set_image(url="attachment://overlay.png")

	# 		msg = await ctx.send(embed=e, file=overlay, filename='overlay.png')
	# 		check = lambda m: m.channel == ctx.channel and m.author == ctx.author \
	# 											and len(m.content) <= 3
	# 		try:
	# 			id_msg = await self.bot.wait_for('message', check=check, timeout=20)
	# 		except asyncio.TimeoutError:
	# 			return await ctx.send('\N{WARNING SIGN} `Face selection timed out...`', delete_after=5)
	# 		finally:
	# 			if id_msg:
	# 				await ctx.delete(msg, id_msg, error=False)

	# 		ids = id_msg.content
	# 		if ids == 'all':
	# 			ids = faces[:5]
	# 		else:
	# 			match = re.findall(r"(\d)\,*", ids)
	# 			if match:
	# 				ids = [faces[int(x) - 1] for x in match if x.isdigit() and int(x) <= fl]
	# 		if not ids or not isinstance(ids, list):
	# 			return await ctx.send('\N{NO ENTRY} `Invalid face selection!`')
	# 	else:
	# 		ids = faces

	# 	m = await ctx.send('ok, processing')
	# 	faces = [f['id'] for f in ids]
	# 	for idx, face in enumerate(faces):
	# 		if idx != 0:
	# 			load = await self.upload_faceapp(ctx, b)
	# 			if not load:
	# 				if idx > 1:
	# 					break
	# 				return
	# 			code, nfaces = load
	# 			if face not in nfaces:
	# 				continue
	# 		ep = f"{self.fa_api}/{code}/"
	# 		if not isinstance(filter_name, str):
	# 			styles = ','.join(filter_name)
	# 			ep += f"{editor}?filters={quote(styles)}&"
	# 		else:
	# 			ep += f"filters/{filter_name}?"
	# 		ep += f"face_at={quote(face)}&no-watermark=1"
	# 		b = await self.bytes_download(ep, headers=self.fa_headers, timeout=15)

	# 	await asyncio.gather(
	# 		ctx.send(file=b, filename=f'{filter_name}.png'),
	# 		ctx.delete(m, error=False)
	# 	)

	@staticmethod
	def gen_fa_did():
		return str(uuid4()).upper()

	async def get_faceapp_token(self):
		api = 'https://api.faceapp.io/api/v2.8/subscriptions/apple'
		payload = {
			"receipt_data": self.fa_itunes,
			"sandbox": False
		}
		headers = {
			"user-agent": self.fa_ua,
			"x-faceapp-deviceid": self.fa_did
		}
		r = await self.post_data(api, payload, headers=headers, json=True)
		if r and 'token' in r:
			return r['token']

	async def faceapp_request(self, ctx, url, filter_name, cropped=False):
		if filter_name not in self.fa_free_no_crop:
			return await ctx.send(f'\N{WARNING SIGN} `This filter is no longer available because FaceApp removed it`')
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		api = "https://node-01.faceapp.io/api/v2.3/photos"
		o = await self.bot.is_owner(ctx.author)
		headers = {
			"user-agent": self.fa_ua,
			"x-faceapp-deviceid": self.gen_fa_did()
		}
		if o:
			headers['x-faceapp-subscription'] = await self.get_faceapp_token()
			headers['x-faceapp-deviceid'] = self.fa_did
		elif not cropped and filter_name not in self.fa_free_no_crop:
			cropped = True
		b = await self.generic_api('faceapp_pad', url)
		data = {'file': b}
		load = await self.proxy_request('post', api, data=data, headers=headers,
																		json=True, rheaders=True, timeout=25)
		if not load or 'code' not in load[0]:
			if load:
				try:
					error = load[1]['X-FaceApp-ErrorCode']
				except KeyError:
					msg = 'Ratelimited, try again.'
				else:
					if error == 'photo_bad_type':
						msg = 'Invalid image provided.'
					elif error == 'photo_no_faces':
						msg = 'No faces detected on provided image.'
					else:
						msg = 'Invalid human image for filter.'
			else:
				msg = 'API timed out...'
			return await ctx.send(f'\N{WARNING SIGN} `{msg}`')
		code = load[0]['code']
		ep = f'{api}/{code}/filters/{filter_name}?cropped={int(cropped)}'
		b = await self.proxy_request('get', ep, headers=headers,
																	b=True, timeout=15)
		b = await self.generic_api('faceapp_crop', body=b.read())
		await ctx.send(file=b, filename=f'{filter_name}.png')

	# --- SMILES ---

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def smile(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def smile2(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "smile_2")

	@commands.command(aliases=['tight'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def tightsmile(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "smile_tight")

	@commands.command(aliases=['sad'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def frown(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	# --- IMPRESSIONS ---

	# @commands.command(aliases=['imp', 'hot', 'hollywood', 'hw'])
	# @commands.cooldown(2, 5, commands.BucketType.guild)
	# async def impression(self, ctx, *, url:str=None):
	# 	await self.faceapp_request(ctx, url, ctx.command.name)

	# @commands.command(aliases=['hot2'])
	# @commands.cooldown(2, 5, commands.BucketType.guild)
	# async def wave(self, ctx, *, url:str=None):
	# 	await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def hot(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def hot2(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, 'wave')

	@commands.command(aliases=['hw'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def hollywood(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name, True)

	@commands.command(aliases=['imp'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def impression(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command(aliases=['mup'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def makeup(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command(aliases=['mup2'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def makeup2(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "makeup_2")

	# --- AGES ---

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def old(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def young(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	# --- HAIR COLORS ---

	@commands.command(aliases=['blackhair'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def black(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "black_hair")

	@commands.command(aliases=['blondhair', 'blonde'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def blond(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "blond_hair")

	@commands.command(aliases=['brownhair'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def brown(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "brown_hair")

	@commands.command(aliases=['redhair'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def red(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "red_hair")

	@commands.command(aliases=['tintedhair']) # dirty blonde
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def tinted(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "tinted_hair")

	# --- BEARDS ---

	@commands.command(aliases=['hip'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def hipster(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command(aliases=['goat'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def goatee(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command(aliases=['must', 'stache'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def mustache(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	# @commands.command(aliases=['pan'])
	# @commands.cooldown(2, 5, commands.BucketType.guild)
	# async def beard(self, ctx, *, url:str=None):
	# 	await self.faceapp_request(ctx, url, "full_beard")

	@commands.command(aliases=['pan'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def beard(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, 'pan', True)

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def shaved(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command(aliases=['ggoat', 'grand'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def grandgoatee(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "grand_goatee")

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def lion(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command(aliases=['pgoat', 'petite'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def petitegoatee(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "petit_goatee")

	# --- GLASSES ---

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def glasses(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command(aliases=['sung'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def sunglasses(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	# --- HAIR STYLES ---

	@commands.command(aliases=['bang'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def bangs(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "bangs_2")

	@commands.command(aliases=['hit'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def hitman(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name, True)

	@commands.command(aliases=['long'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def longhair(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "long_hair")

	@commands.command(aliases=['wavyhair'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def wavy(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, ctx.command.name)

	@commands.command(aliases=['straighthair'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def straight(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "straight_hair")

	@commands.command(aliases=['walter', 'ww'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def heisenberg(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "heisenberg", True)

	# --- GENDERS ---

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def male(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "male", True)

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def female(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "female", True)

	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def female2(self, ctx, *, url:str=None):
		await self.faceapp_request(ctx, url, "female_2", True)

	# # --- Stylist ---

	# fa_map = {
	# 	"stylist": {
	# 		"hair-colors": {
	# 			"black": "black_hair",
	# 			"blond": "blond_hair",
	# 			"brown": "brown_hair",
	# 			"red": "red_hair",
	# 			"tinted": "tinted_hair"
	# 		},
	# 		"hair-styles": {
	# 			"bangs": "bangs_2",
	# 			"hitman": None,
	# 			"long": "long_hair",
	# 			"wavy": None,
	# 			"straight": "straight_hair"
	# 		},
	# 		"glasses": {
	# 			"glasses": None,
	# 			"sunglasses": None
	# 		},
	# 		"beards": {
	# 			"goatee": None,
	# 			"mustache": None,
	# 			"beard": "full_beard",
	# 			"shaved": None,
	# 			"grand": "grand_goatee",
	# 			"hipster": None,
	# 			"lion": None,
	# 			"petite": "petit_goatee"
	# 		}
	# 	},
	# 	"editor": {
	# 		"impression": {
	# 			"hollywood": "impression",
	# 			"wave": None,
	# 			"makeup": None,
	# 			"makeup2": "makeup_2"
	# 		},
	# 		"smiles": {
	# 			"smile": "smile_2",
	# 			"smile2": "smile_3",
	# 			"tight": "smile_tight",
	# 			"tightsmile": "smile_tight",
	# 			"frown": None,
	# 			"sad": "frown"
	# 		},
	# 		"age": {
	# 			"old": None,
	# 			"young": None
	# 		}
	# 	}
	# }

	# @commands.command(aliases=['style'])
	# @commands.cooldown(2, 5, commands.BucketType.guild)
	# async def stylist(self, ctx, *styles:str):
	# 	"""Multiple effects with crop"""
	# 	if not styles:
	# 		raise commands.MissingRequiredArgument(ctx.author)

	# 	fmap = self.fa_map['stylist']
	# 	url = styles[0]
	# 	# make sure url isn't a style: to fetch last attachment
	# 	if any([url == x for x in fmap[y]] for y in fmap):
	# 		url = None
	# 	else:
	# 		styles = styles[1:]

	# 	if len(styles) < 2:
	# 		return await ctx.send(
	# 			"\N{NO ENTRY} Atleast **2** styles are needed! " \
	# 			"Use the `styles` command to view all available styles."
	# 		)

	# 	# preserve order of styles
	# 	apply = {x: None for x in fmap}
	# 	for style in styles:
	# 		for cat in fmap:
	# 			scat = fmap[cat]
	# 			for sty in scat:
	# 				if sty == style:
	# 					apply[cat] = (scat[sty] or sty) + "-stylist"

	# 	await self.faceapp_request(ctx, url, apply.values())

	# @commands.command()
	# @commands.cooldown(1, 5, commands.BucketType.guild)
	# async def styles(self, ctx):
	# 	e = discord.Embed()
	# 	e.title = "FaceApp Stylist Styles",
	# 	e.color = discord.Color.blue()
	# 	fmap = self.fa_map['stylist']
	# 	for category in fmap:
	# 		e.add_field(name=category, value="\n".join(fmap[category]))
	# 	await ctx.send(embed=e)

	# @commands.command()
	# @commands.cooldown(2, 5, commands.BucketType.guild)
	# async def editor(self, ctx, *styles:str):
	# 	if not styles:
	# 		raise commands.MissingRequiredArgument(ctx.author)

	# 	# merge all styles
	# 	fmap = {**self.fa_map['stylist'], **self.fa_map['editor']}
	# 	url = styles[0]
	# 	# make sure url isn't a style: to fetch last attachment
	# 	if any([url == x for x in fmap[y]] for y in fmap):
	# 		url = None
	# 	else:
	# 		styles = styles[1:]

	# 	if len(styles) < 1:
	# 		return await ctx.send(
	# 			"\N{NO ENTRY} Atleast **1** style is needed! " \
	# 			"Use the `edits` command to view all available edits."
	# 		)

	# 	apply = []
	# 	for style in styles:
	# 		for cat in fmap:
	# 			scat = fmap[cat]
	# 			for sty in scat:
	# 				if sty == style:
	# 					apply.append(scat[sty] or sty)

	# 	await self.faceapp_request(ctx, url, apply, "editor")

	# @commands.command()
	# @commands.cooldown(1, 5, commands.BucketType.guild)
	# async def edits(self, ctx):
	# 	e = discord.Embed()
	# 	e.title = "FaceApp Editor Styles"
	# 	e.description = 'Certain styles have aliases: e.g. "frown" and "sad" are the same thing.'
	# 	e.color = discord.Color.blue()
	# 	fmap = self.fa_map
	# 	for m in fmap:
	# 		for category in m:
	# 			e.add_field(name=category, value="\n".join(m[category]))
	# 	await ctx.send(embed=e)


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def implode(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=200, float=True)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		scale = scale or 1
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, scale=scale)
			await ctx.send(file=final, filename='implode.png', content=scale_msg)


	@commands.command(aliases=['exp'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def explode(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=-200,
																			 float=True, negative=True, make_negative=True)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		scale = scale or -1
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, scale=scale)
			await ctx.send(file=final, filename='explode.png', content=scale_msg)


	@commands.command(aliases=['cblur', 'radial'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def circle(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=360)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		scale = scale or 8
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, scale=scale)
			await ctx.send(file=final, filename='circlular_blur.png', content=scale_msg)


	@commands.command(aliases=['bulge', 'fish'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def fisheye(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='fisheye.png')


	@commands.command(aliases=['df'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def deepfry(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=100)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		scale = scale or 10
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, scale=scale)
			await ctx.send(file=final, filename='deepfry.png', content=scale_msg)


	@commands.group(aliases=['sc', 'thot'], invoke_without_command=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0], text='dog')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='dog2', aliases=['d2'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_dog2(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='dog2')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='bunny', aliases=['b'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_bunny(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='bunny')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='cat', aliases=['c'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_cat(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='cat')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='cat2', aliases=['c2'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_cat2(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='cat2')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='heart', aliases=['h'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_heart(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='heart')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='flowers', aliases=['f'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_flowers(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='flowers')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='flowers2', aliases=['f2'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_flowers2(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='flowers2')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='devil', aliases=['d'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_devil(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='devil')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='glasses', aliases=['g'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_glasses(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='glasses')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='moustache', aliases=['m'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_moustache(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='moustache')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='angery', aliases=['a'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_angery(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='angery')
		await ctx.send(file=final, filename='snapchat.png')

	@snapchat.command(name='sunglasses', aliases=['sg'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def snapchat_sunglasses(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='sunglasses')
		await ctx.send(file=final, filename='snapchat.png')


	@commands.command(aliases=['mojo'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def watchmojo(self, ctx, url:str, *, txt:str):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		for url in get_images:
			final = await self.f_api(ctx.command.name, url, text=txt)
			await ctx.send(file=final, filename='watchmojo.png')


	@commands.command(aliases=['kekflag'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def kekistan(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='kekistan.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def disabled(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='disabled.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def composite(self, ctx, *urls:str):
		if len(urls) < 2:
			return await ctx.send('\N{NO ENTRY} Command requires atleast 2 images.')
		get_images = await self.get_images(ctx, urls=urls, limit=20)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, *get_images)
		await ctx.send(file=final, filename='composite.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def nooseguy(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='nooseguy.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def owo(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='owo.png')


	@commands.command(aliases=['paint'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def idubbbz(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='painting.png')


	@commands.command(aliases=['gspeed'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gifspeed(self, ctx, *urls:str):
		"""Use negative speeds to make it slower."""
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=50, gif=True, negative=True)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		scale = scale or 2
		for url in get_images:
			final = await self.generic_api(ctx.command.name, url, scale=scale)
			await ctx.send(file=final, filename='gifspeed.gif', content=scale_msg)


	@commands.command(aliases=['shoe'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def shit(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='shit.png')


	@commands.command(aliases=['paint2', 'ross', 'bob'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def bobross(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='bobross.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def perfection(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='perfection.png')


	@commands.command(aliases=["worsethanhitler"])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def wth(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='wth.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def mistake(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='mistake.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def reminder(self, ctx, url:str, *, txt:str):
		get_images = await self.get_images(ctx, urls=url, limit=2)
		if not get_images:
			return
		for url in get_images:
			final = await self.f_api(ctx.command.name, url, text=txt)
			await ctx.send(file=final, filename='reminder.png')


	@commands.command(aliases=['zuck', 'zucc'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def zuckerberg(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='zuckerberg.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def ugly(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='ugly.png')


	# @commands.command()
	# @commands.cooldown(1, 5, commands.BucketType.guild)
	# async def noise(self, ctx, *, url:str):
	# 	get_images = await self.get_images(ctx, urls=url)
	# 	if not get_images:
	# 		return
	# 	url = get_images[0]
	# 	b = await self.bytes_download(url)
	# 	args = ['convert', '-', '-resize', '512x512>']
	# 	amp = 20
	# 	while amp < 30:
	# 		args.extend([
	# 			'(',
	# 				'-clone', '0',
	# 				'-noise', str(amp),
	# 				'-attenuate', str(amp),
	# 			')'
	# 		])
	# 		amp += 1
	# 	amp = 30
	# 	while amp >= 20:
	# 		args.extend([
	# 			'(',
	# 				'-clone', '0',
	# 				'-noise', str(amp),
	# 				'-attenuate', str(amp),
	# 			')'
	# 		])
	# 		amp -= 1
	# 	args.extend([
	# 		'-delay', '4',
	# 		'-set', 'delay', '4',
	# 		'-loop', '0',
	# 		'gif:-'
	# 	])
	# 	final = await self.run_process(args, b=True, stdin=b)
	# 	await ctx.send(file=final, filename='noise.gif')


	@commands.command(aliases=['cg'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def coolguy(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='coolguy.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def god(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='god.png')


	@commands.command(aliases=['gabe'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gaben(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='gaben.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def autism(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='autism')
		await ctx.send(file=final, filename='autism.png')


	@commands.command(aliases=['snapple', 'fact'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def realfact(self, ctx, *, text:commands.clean_content):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='realfact.png')

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def dork(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='dork.png')


	@commands.command(aliases=['squidward'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def art(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text='squidward')
		await ctx.send(file=final, filename='art.png')


	@commands.command()
	@commands.cooldown(2, 3, commands.BucketType.guild)
	async def p90(self, ctx, *tags:str):
		api = f"https://p90.zone/api/search/{','.join(tags)}" \
					if tags else "https://p90.zone/api/random"
		load = await self.get_json(api, headers={'Authorization': 'Bearer fa2dfda8-ba01-4a2a-99a5-ff15551507e8'})
		if not load:
			return await ctx.send('\N{WARNING SIGN} `No results found on` <https://p90.zone>')
		if not tags:
			load = [load]
		images = [f"https://push.p250.zone/t/{x['name']}.png" for x in load]
		url = "[{0}](https://p90.zone/{0})\n"
		descs = [f"{url.format(x['name'])}\n`{x['views']} Views`" for x in load]
		try:
			p = Pages(ctx, entries=images, descriptions=descs, images=True, minimal=True)
			p.embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url or ctx.author.default_avatar_url)
			await p.paginate()
		except CannotPaginate:
			await ctx.send(f"https://p90.zone/{random.choice(load)['name']}")


	@commands.command(aliases=['9gag'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def ninegag(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('9gag', get_images[0])
		await ctx.send(file=final, filename='9gag.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def adidas(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='adidas.png')


	@commands.command(aliases=['adminwalk'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def adw(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='adw.png')


	@commands.command(aliases=['murica', 'usa'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def america(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='america.png')


	@commands.command(aliases=['alevel'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def autismlevel(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('autism', get_images[0])
		await ctx.send(file=final, filename='autism.png')


	@commands.command(aliases=['bandi'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def bandicam(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='bandicam.png')


	@commands.command(aliases=['condomfail'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def condom(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='condomfail.png')


	@commands.command(aliases=['depr'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def depression(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='depression.png')


	async def do_hacker(self, ctx, txt:str, template=0):
		final = await self.f_api("hacker", text=txt, template=template)
		await ctx.send(file=final, filename='hacker.png')

	@commands.group(aliases=['hack'], invoke_without_command=True)
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def hacker(self, ctx, *, text:commands.clean_content):
		"""
		Alias for the template is also the command number (e.g. ".hacker 2" instead of ".hacker connor").
		"""
		await self.do_hacker(ctx, text)

	@hacker.command(name='connor', aliases=['2', 'c'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def hacker_connor(self, ctx, *, text:commands.clean_content):
		await self.do_hacker(ctx, text, 1)


	@commands.command(aliases=['star'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def goldstar(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='goldstar.png')


	@commands.command(aliases=['hcam'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def hypercam(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='hypercam.png')


	@commands.command(aliases=['challenge'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def jackoff(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='jackoff_challenge.png')


	@commands.command(aliases=['keem'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def keemstar(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='keemstar.png')


	@commands.command(aliases=['nk'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def northkorea(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='northkorea.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def portal(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='nooseportal.png')


	@commands.command(aliases=['phc', 'phcaption'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def pornhubcaption(self, ctx, url:str, *, text:commands.clean_content):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		for url in get_images:
			final = await self.f_api('pornhub', url, text=text)
			await ctx.send(file=final, filename='pornhub.png')


	@commands.command(aliases=['respect'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def respects(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='respects.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def russia(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='russia.png')


	@commands.command(aliases=['shootings'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def shooting(self, ctx, *, text:commands.clean_content):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='shootings.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def spain(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='spain.png')


	@commands.command(aliases=['stockphoto'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def stock(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='stockphoto.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def ussr(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='ussr.png')


	@commands.command(aliases=['unitedkingdom'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def uk(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='uk.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def ifunny(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='ifunny.png')


	@commands.command(aliases=['swap'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def faceswap(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='faceswap.png')


	@commands.command(aliases=['pixel2'])
	@commands.cooldown(2, 5)
	async def pixelate2(self, ctx, *urls):
		get_images = await self.get_images(ctx, urls=urls, limit=2, scale=512)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		for url in get_images:
			final = await self.f_api('pixelate', url, amount=max(2, scale or 10))
			await ctx.send(file=final, filename='pixelated.png', content=scale_msg)


	@commands.command(aliases=['gsharp'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gsharpen(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, gif=True, scale=100, limit=1)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url, scale=scale or 15)
		await ctx.send(file=final, filename='gsharpen.gif', content=scale_msg)


	@commands.command(aliases=['christmas', 'hat'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def santahat(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images, text='christmas')
		await ctx.send(file=final, filename='santahat.png')


	@commands.command(aliases=['sanders', 'congress'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def bernie(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='bernie.png')


	@commands.command(aliases=['thuglife'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def thug(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text=ctx.command.name)
		await ctx.send(file=final, filename='thuglife.png')


	#wtf super
	def get_index(self, l, obj):
		try:
			return l.index(obj)
		except ValueError:
			return -1

	async def do_emojify(self, args, vertical=False):
		bg = '\N{FACE WITH TEARS OF JOY}'
		fg = '\N{NEGATIVE SQUARED LATIN CAPITAL LETTER B}'
		args = [(bool(await self.emoji_path(x, verify=True)), x)
						for x in args]
		if any(x[0] for x in args):
			eargs = [x for x in args if x[0]]
			bg = eargs[0]
			if len(eargs) > 1:
				fg = eargs[1]
		text = ' '.join([
			x[1] for i, x in enumerate(args) \
			if not x[0] or not any(self.get_index(args, y) == i \
			for y in (bg, fg))
		])
		args = {
			'background': bg[1] if isinstance(bg, tuple) else bg,
			'foreground': fg[1] if isinstance(fg, tuple) else fg,
			'text': text.strip()[:32]
		}
		e = await self.f_api('emojify', raw=True, vertical=vertical, **args)
		return f"```{e[:1994]}```"
	#end wtf-cxfdz

	@commands.group(aliases=['efy'], invoke_without_command=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def emojify(self, ctx, *args:str):
		if not args:
			return await ctx.send('\N{NO ENTRY} `Missing text argument.`')
		await ctx.send(await self.do_emojify(args))

	@emojify.command(name='vertical', aliases=['v', 'vert'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def emojify_vertical(self, ctx, *args:str):
		if not args:
			return await ctx.send('\N{NO ENTRY} `Missing text argument.`')
		await ctx.send(await self.do_emojify(args, True))


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def zoom(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='zoom.png')


	# Kairos removed for now.
	# @commands.command(aliases=['diversity', 'kairos'])
	# @commands.cooldown(1, 5, commands.BucketType.guild)
	# async def races(self, ctx, *urls:str):
	# 	get_images = await self.get_images(ctx, urls=urls, limit=1, default_mimes=True)
	# 	if not get_images:
	# 		return
	# 	b = await self.bytes_download(get_images[0], proxy=True)
	# 	payload = FormData()
	# 	img = json.dumps({
	# 		"image": b64encode(b.read()).decode(),
	# 		"minHeadScale": ".015",
	# 		"show_uploaded_image": True
	# 	})
	# 	payload.add_field("imgObj", img)
	# 	payload.add_field("fileType", "image/png")
	# 	load = await self.get_json("https://demo2.kairos.com/facerace/send-to-api",
	# 														 data=payload, content_type=None)
	# 	if not load or 's3_image_url' not in load:
	# 		return await ctx.send("\N{NO ENTRY} `Kairos errored or returned nothing.`")
	# 	elif "Errors" in load:
	# 		err = '\n'.join([x['Message'] for x in load['Errors']])
	# 		return await ctx.send(f"\N{WARNING SIGN} `{err}`")
	# 	final = await self.bytes_download(load['s3_image_url'])
	# 	await ctx.send(file=final, filename='kairos.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gimp(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('resize', get_images[0])
		await ctx.send(file=final, filename='gimp.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def sonic(self, ctx, *, txt:commands.clean_content):
		final = await self.f_api(ctx.command.name, text=txt)
		await ctx.send(file=final, filename='sonic.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def trans(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='trans.png')


	@commands.command(aliases=['pai', 'ajitpai'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def ajit(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='ajit.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def joy(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text=ctx.command.name)
		await ctx.send(file=final, filename='joy.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def thinking(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text=ctx.command.name)
		await ctx.send(file=final, filename='thinking.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def think(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, scale=100, limit=2)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		for url in get_images:
			final = await self.f_api('thinking', url, level=scale or 50)
			await ctx.send(content=scale_msg, file=final, filename='think.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def yusuke(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='yusuke.png')


	@commands.command()
	@commands.cooldown(2, 5)
	async def zalgo(self, ctx, *, text:commands.clean_content):
		chars = [chr(x) for x in range(768, 879)]
		await ctx.send("".join(
			c + "".join(
				random.choice(chars) for _
				in range(random.randint(2, 7) * c.isalnum())
			) for c in text
		))


	@commands.command(aliases=['nsb'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def notsobot(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api('snapchat', get_images[0], text=ctx.command.name)
		await ctx.send(file=final, filename='notsobot.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def jack(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='jack.png')


	@commands.command(aliases=['hebrew', 'jewish'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def israel(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='israel.png')


	@commands.command(aliases=['loganpaul'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def logan(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='logan.png')


	@commands.command(aliases=['gdf'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gdeepfry(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, gif=True, scale=100, limit=1)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url, scale=scale or 10)
		await ctx.send(file=final, filename='gdeepfry.gif', content=scale_msg)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def blackify(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='blackify.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def trump(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='trump.png')


	@commands.command(aliases=['panther', 'bp'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def blackpanther(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='blackpanther.png')


	@commands.command(aliases=['spacex'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def starman(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='starman.png')


	@commands.command(aliases=['ginvert2'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def flash(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, scale=2000, limit=1)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		scale = max(scale, 20) if scale else 80
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url, scale=scale)
		await ctx.send(file=final, filename='flash.gif', content=scale_msg)


	@commands.command(aliases=['gex', 'gexp'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gexplode(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=1, scale=6)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url, scale=scale or 4)
		await ctx.send(file=final, filename='gexplode.gif', content=scale_msg)


	@commands.command(aliases=['gim', 'gimpl'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def gimplode(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=1, scale=6)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images
		url = get_images[0]
		final = await self.generic_api(ctx.command.name, url, scale=scale or 4)
		await ctx.send(file=final, filename='gimplode.gif', content=scale_msg)


	@commands.command(aliases=['wiki', 'how'])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def wikihow(self, ctx, *, text:str):
		r = await self.f_api(ctx.command.name, text=text, json=True)
		if not r or not isinstance(r, dict):
			return await ctx.send("\N{WARNING SIGN} `Invalid Search.`")
		e = discord.Embed.from_dict(r)
		await ctx.send(embed=e)


	@commands.command(aliases=['cmm'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def changemymind(self, ctx, *, text:str):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='changemymind.png')


	@commands.command(aliases=['hypebeast'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def supreme(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='supreme.png')


	async def parse_quote(self, ctx, message, user, text, og=True):
		for m in message.mentions:
			text = text.replace(m.mention, f"[@{m.display_name}]")
		text = text.replace('<a:', '<:')
		compact = light = False
		if og:
			if ' -light' in text:
				light = True
				text = text.replace(' -light', '')
			if ' -compact' in text:
				compact = True
				text = text.replace(' -compact', '')
		t = message.edited_at or message.created_at
		fmt = "%-I:%M %p"
		if compact is False:
			d = datetime.now() - t
			if 0 <= d.days <= 6:
				fmt = f"{'Last %A' if d.days else 'Today'} at {fmt}"
			else:
				fmt = r"%m/%d/%Y"
		t = t.strftime(fmt)
		args = {
			"message": {
				"content": text,
				"embed": message.embeds[0].to_dict() \
								 if message.embeds else None
			},
			"author": {
				"username": user.display_name,
				"color": str(self.get_role_color(user)),
				"avatarURL": str(user.avatar_url_as(format='png', size=128)),
				"bot": user.bot
			},
			"timestamp": t,
			"light": light,
			"compact": compact
		}
		final = await self.f_api('quote', **args)
		await ctx.send(file=final, filename='quote.png')

	@commands.group(invoke_without_command=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def quote(self, ctx, *, text:str):
		"""Use flags such as "-compact" or "-light" to change the theme."""
		user = ctx.author
		m = ctx.message.mentions
		sp = text.split()
		f = sp[0]
		s = False
		if m and f == m[0].mention:
			user = m[0]
			s = True
		elif (f.startswith('<@') and f.endswith('>')) or self.is_id(f):
			u = await self.bot.funcs.find_member(ctx.message, f)
			if u:
				user = u
				s = True
		if s:
			text = " ".join(sp[1:])
		await self.parse_quote(ctx, ctx.message, user, text)

	@quote.command(name='id', aliases=['message', 'user'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def quote_id(self, ctx, msg:MemberOrMessage, *, text:str=""):
		if isinstance(msg, discord.Message):
			user = msg.author
			t = msg.content
		else:
			user = msg
			t = None
			async for m in ctx.channel.history(limit=100, before=ctx.message):
				if m.author == user:
					t = m.content
					msg = m
					break
			if t is None:
				return await ctx.send("\N{WARNING SIGN} No messages found by " \
														  f"`{user}` within **100** searched messages!")
		await self.parse_quote(ctx, msg, user, f"{t} {text}", og=False)


	@commands.command(aliases=['e2p', 'edgestoporn'])
	@checks.nsfw()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def edges2porn(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='edges2porn.png')


	@commands.command(aliases=['e2e', 'edgestoemojis'])
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def edges2emojis(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='edges2emojis.png')


	@commands.command(aliases=['hawk', 'stephen'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def hawking(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='hawking.png')


	@commands.command(aliases=['evalm'])
	@checks.owner_or_ids(687945863053443190)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def evalmagik(self, ctx, url:str, *, args:str):
		for i in range(2):
			get_images = await self.get_images(ctx, urls=url, limit=1, gif=bool(i))
			if get_images:
				break
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0], text=args)
		await ctx.send(file=final, filename='imagemagick.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def rain(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='rain.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def gold(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='gold.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def gold2(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='gold2.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def exo(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='exo.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def kek(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='kek.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def kek2(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='kek2.png')


	@commands.command(aliases=['napkin'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def paper(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='paper.png')


	@commands.command(aliases=['globe'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def bubble(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='bubble.png')


	@commands.command(aliases=['tun'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def tunnel(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0], mode=2)
		await ctx.send(file=final, filename='tunnel.png')


	@commands.command(aliases=['tun2'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def tunnel2(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api('tunnel', get_images[0], mode=1)
		await ctx.send(file=final, filename='tunnel2.png')


	@commands.command(aliases=['blurp'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def blurple(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='blurple.png')


	async def store_photofunia(self, b):
		payload = FormData()
		payload.add_field('image', b, filename='image.png', content_type='image/png')
		r = await self.proxy_request('post', 'https://photofunia.com/images?server=2',
																 data=payload, json=True, timeout=20)
		assert r and 'error' not in r
		return r['response']['key']

	async def process_photofunia(self, ctx, cat, payload, effect, img=None):
		if payload is None:
			payload = FormData()
		url = f"https://photofunia.com/categories/{cat}/{effect}?server=2"
		payload.add_field('current-category', cat)
		if img:
			b = await self.bytes_download(img, proxy=True)
			try:
				img = await self.store_photofunia(b)
			except AssertionError:
				return await ctx.send('\N{NO ENTRY} `Something is wrong with your photo (size, validity).`')
			payload.add_field('image', img)
		try:
			r = await self.proxy_request('post', url, data=payload, timeout=20)
			assert r
			url = r.url
			if str(url).endswith('no_faces'):
				return await ctx.send("\N{NO ENTRY} `Face not detected`")
			body = await self.proxy_request('get', r.url, text=True, timeout=20)
			assert body
			match = self.photofunia_regex.search(body)
			assert match
			e = discord.Embed()
			e.set_image(url=match.group())
			await ctx.send(embed=e)
		except AssertionError:
			await ctx.send('\N{WARNING SIGN} `API Failed.`')


	@commands.command(aliases=['uni'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def universe(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=1, scale=4)
		if not get_images:
			return
		get_images, scale, _ = get_images
		url = get_images[0]
		payload = FormData()
		payload.add_field('type', f"space{max(1, scale or 2)}")
		await self.process_photofunia(ctx, 'lab', payload,
																	'you-are-my-universe', img=url)


	@commands.command(aliases=['ein', 'stein'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def einstein(self, ctx, *, text:str):
		payload = FormData()
		payload.add_field('text', text[:15])
		await self.process_photofunia(ctx, 'lab', payload, ctx.command.name)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def fat(self, ctx, *urls:str):
		get_images = await self.get_images(ctx, urls=urls, limit=1, scale=3)
		if not get_images:
			return
		get_images, scale, _ = get_images
		if scale == 0:
			scale = 1
		else:
			scale = 3
		url = get_images[0]
		payload = FormData()
		payload.add_field('size', ("XXXL", "XXXXL", "XXXXXL")[scale - 1])
		await self.process_photofunia(ctx, 'lab', payload,
																	'fat_maker', img=url)


	@commands.command(aliases=['100'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def bill(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		await self.process_photofunia(ctx, 'lab', None,
																	'100_dollars', img=url)


	async def do_anime(self, ctx, url, color='norm'):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		payload = FormData()
		payload.add_field('eyes', color)
		await self.process_photofunia(ctx, 'lab', payload,
																	'anime', img=url)

	@commands.group(aliases=['animeyes', 'animeeyes'], invoke_without_command=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def anime(self, ctx, *, url:str=None):
		await self.do_anime(ctx, url)

	@anime.command(name='blue', aliases=['1'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def anime_blue(self, ctx, *, url:str=None):
		await self.do_anime(ctx, url, 'blue')

	@anime.command(name='aqua', aliases=['2'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def anime_aqua(self, ctx, *, url:str=None):
		await self.do_anime(ctx, url, 'aqua')

	@anime.command(name='green', aliases=['3'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def anime_green(self, ctx, *, url:str=None):
		await self.do_anime(ctx, url, 'green')

	@anime.command(name='brown', aliases=['4'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def anime_brown(self, ctx, *, url:str=None):
		await self.do_anime(ctx, url, 'brown')

	@anime.command(name='red', aliases=['5'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def anime_red(self, ctx, *, url:str=None):
		await self.do_anime(ctx, url, 'red')

	@anime.command(name='purple', aliases=['6'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def anime_purple(self, ctx, *, url:str=None):
		await self.do_anime(ctx, url, 'purple')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def clown(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		await self.process_photofunia(ctx, 'lab', None,
																	'clown', img=url)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def alien(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		payload = FormData()
		payload.add_field('skin', 'on')
		await self.process_photofunia(ctx, 'lab', payload,
																	'alien', img=url)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def soup(self, ctx, *, text:str):
		payload = FormData()
		payload.add_field('text', text[:14])
		await self.process_photofunia(ctx, 'lab', payload, "soup_letters")


	@commands.command(aliases=['rushmore'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def mount(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		await self.process_photofunia(ctx, 'faces', None,
																	'mount_rushmore', img=url)


	@commands.command(aliases=['sphere', 'galatea'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def spheres(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		await self.process_photofunia(ctx, 'frames', None,
																	'galatea', img=url)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def museum(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		await self.process_photofunia(ctx, 'frames', None,
																	'museum_kid', img=url)


	@commands.command(aliases=['burning'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def burn(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		payload = FormData()
		payload.add_field('animation', 'icon')
		await self.process_photofunia(ctx, 'all_effects', payload,
																	'burning_photo', img=url)


	@commands.command(aliases=['pop'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def popart(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		payload = FormData()
		payload.add_field('size', '2x2')
		await self.process_photofunia(ctx, 'all_effects', payload,
																	ctx.command.name, img=url)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def center(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.generic_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='center.png')


	@commands.command(aliases=['ge2p'])
	@commands.cooldown(1, 7, commands.BucketType.guild)
	async def gedges2porn(self, ctx, *, url:str=None):
		try:
			x = await ctx.send("ok, processing (this might take a while)")
			get_images = await self.get_images(ctx, urls=url, gif=True, limit=1)
			if not get_images:
				return
			url = get_images[0]
			final = await self.f_api('edges2porn_gif', url)
			await ctx.send(file=final, filename='edges2porn.gif')
		finally:
			await ctx.delete(x, error=False)


	@commands.command(aliases=['faceoverlay'])
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def overlay(self, ctx, *urls:str):
		if len(urls) < 2:
			return await ctx.send('\N{NO ENTRY} Command requires 2 images (human-face(s), overlay).')
		get_images = await self.get_images(ctx, urls=urls, limit=2)
		if not get_images:
			return
		final = await self.f_api("face_overlay", *get_images)
		await ctx.send(file=final, filename='face_overlay.png')


	@commands.command()
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def grill(self, ctx, *, text:str):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='grill.png')


	@commands.command(aliases=['simpsons'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def days(self, ctx, *, text:str):
		fw = text.split(maxsplit=1)[0]
		if fw != "with":
			fw = None
		else:
			text = text[5:]
		final = await self.f_api(ctx.command.name, text=text, option=fw)
		await ctx.send(file=final, filename='days.png')


	async def do_facemagik(self, ctx, url, effect='magik'):
		option = None
		if url:
			if url.startswith('-'):
				url = f" {url}"
			if ' -eyes' in url:
				option = 'eyes'
				url = url.replace(' -eyes', '')
			elif ' -mouth' in url:
				option = 'mouth'
				url = url.replace(' -mouth', '')
			if option and not url:
				url = None
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api("face_magik", get_images[0], text=effect, option=option)
		await ctx.send(file=final, filename='face_magik.png')

	@commands.group(aliases=['fm'], invoke_without_command=True)
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik(self, ctx, *, url:str=None):
		"""
		Append flags " -eyes" or " -mouth" for specific facial feature.
		Alias for the effect is also the command number (e.g. ".fm 1" instead of ".fm explode").
		"""
		await self.do_facemagik(ctx, url)

	@facemagik.command(name='explode', aliases=['1', 'exp'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_explode(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'explode')

	@facemagik.command(name='implode', aliases=['2', 'impl'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_implode(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'implode')

	@facemagik.command(name='swirl', aliases=['3'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_swirl(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'swirl')

	@facemagik.command(name='circle', aliases=['4', 'radial', 'rblur'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_circle(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'circle')

	@facemagik.command(name='blur', aliases=['5'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_blur(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'blur')

	@facemagik.command(name='charcoal', aliases=['6', 'coal'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_charcoal(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'charcoal')

	@facemagik.command(name='tehi', aliases=['7'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_tehi(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'tehi')

	@facemagik.command(name='pixelate', aliases=['8', 'pixel', 'pix'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_pixelate(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'pixelate')

	@facemagik.command(name='spin', aliases=['9'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_spin(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'spin')

	@facemagik.command(name='magika', aliases=['10', 'ma'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_magika(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'magika')

	@facemagik.command(name='rain', aliases=['11'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_rain(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'rain')

	@facemagik.command(name='gold', aliases=['12'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_gold(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'gold')

	@facemagik.command(name='frost', aliases=['13'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_frost(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'frost')

	@facemagik.command(name='pseudocolor', aliases=['pc', '14'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_pc(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'pc')

	@facemagik.command(name='kaleidoscope', aliases=['ks', '15'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_kaleidoscope(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'kaleidoscope')

	@facemagik.command(name='toon', aliases=['16'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_toon(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'toon')

	@facemagik.command(name='ripples', aliases=['rip', '17'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_ripples(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'ripples')

	@facemagik.command(name='emoji', aliases=['e2m', '18'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def facemagik_emoji(self, ctx, *, url:str=None):
		await self.do_facemagik(ctx, url, 'emoji')


	@commands.command()
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def wheeze(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='wheeze.png')


	@commands.command(aliases=['pseudocolor'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def pc(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(
			'magik_script', get_images[0],
			text='pseudocolor', size='384x384>',
			options=[
				'-i', '8',
				'-d', '7'
			], gif=True
		)
		await ctx.send(file=final, filename='pseudocolor.gif')


	@commands.command(aliases=['td'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def textdistort(self, ctx, url:str, *, text:str):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(
			'magik_script', get_images[0],
			text=ctx.command.name, size='712x712>',
			options=[
				'-t', text[:1000],
				'-p', '16',
				'-c', 'black',
				'-b', 'i',
				'-r', '5',
				'-f', 'liberation-sans'
			]
		)
		await ctx.send(file=final, filename='textdistort.png')


	@commands.command(aliases=['td2'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def textdistort2(self, ctx, url:str, *, text:str):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(
			'magik_script', get_images[0],
			text='textdistort', size='712x712>',
			options=[
				'-t', text[:1000],
				'-p', '16',
				'-r', '5'
			]
		)
		await ctx.send(file=final, filename='textdistort2.png')


	@commands.command()
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def wiggle(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(
			'magik_script', get_images[0],
			text=ctx.command.name, size='512x512>',
			options=[
				'-w', '2',
				'-d', '3',
				'-f', '27'
			], gif=True
		)
		await ctx.send(file=final, filename='wiggle.gif')


	@commands.command(aliases=['sg'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def stainedglass(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(
			'magik_script', get_images[0],
			text=ctx.command.name, size='712x712>',
			options=[
				'-k', 'random',
				'-b', '150',
				'-t', '1',
				'-r', '56'
			]
		)
		await ctx.send(file=final, filename='stainedglass.png')


	@commands.command(aliases=['aa', 'abstract'])
	@commands.cooldown(1, 4, commands.BucketType.guild)
	async def pne(self, ctx, *, url:str=None):
		"""Append flags " -invert" / " -i" or " -composite" / " -c" for extra abstraction."""
		option = 1
		if url:
			if ' -composite' in url or ' -c' in url:
				option += 2
				url = url.replace(' -composite', '').replace(' -c', '')
			if ' -invert' in url or ' -i' in url:
				option += 1
				url = url.replace(' -invert', '').replace(' -i', '')
			if option > 1 and not url:
				url = None
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0], option=option)
		await ctx.send(file=final, filename='abstract.png')


	@commands.command(aliases=['oldman'])
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def oldguy(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='oldman.png')


	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def consent(self, ctx, url:str, *, text:commands.clean_content=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0], text=text or ctx.author.display_name)
		await ctx.send(file=final, filename='consent.png')


	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def linus(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='linus.png')


	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def austin(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='austin.png')


	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def pistol(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='pistol.png')


	@commands.command()
	@commands.cooldown(2, 4, commands.BucketType.guild)
	async def shotgun(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='shotgun.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def excuse(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='excuse.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def yacht(self, ctx, *, text:str):
		payload = FormData()
		payload.add_field('text', text[:25])
		await self.process_photofunia(ctx, 'all_effects', payload, ctx.command.name)


	@commands.command(aliases=['alert'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def presidential(self, ctx, *, text:str):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='presidential.png')


	@commands.command(aliases=['kowalski'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def analysis(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='analysis.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def rtx(self, ctx, *urls:str):
		if len(urls) < 2:
			return await ctx.send('\N{NO ENTRY} Command requires atleast 2 images.')
		get_images = await self.get_images(ctx, urls=urls, limit=2)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, *get_images)
		await ctx.send(file=final, filename='rtx.png')


	@commands.command(aliases=['cosgrove'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def miranda(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='miranda.png')


	@commands.command(aliases=['bino'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def binoculars(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='binoculars.png')


	@commands.command(aliases=['race'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def racecard(self, ctx, *, text:commands.clean_content):
		txt = text.split('|')
		if len(txt) != 2:
			return await ctx.send('\N{NO ENTRY} Command requires two strings of text. Use `|` as a delimiter.')
		final = await self.f_api(ctx.command.name, text=txt)
		await ctx.send(file=final, filename='racecard.png')


	@commands.command(aliases=['keem2'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def keemstar2(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='keemstar2.png')


	@commands.command(aliases=['disabled2'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def amidisabled(self, ctx, *, text:commands.clean_content):
		final = await self.f_api('simpsons_disabled', text=text)
		await ctx.send(file=final, filename='amidisabled.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def jesus(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api(ctx.command.name, get_images[0])
		await ctx.send(file=final, filename='jesus.png')


	@commands.command(aliases=['captcha'])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def recaptcha(self, ctx, *, text:commands.clean_content):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='recaptcha.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def wonka(self, ctx, *, text:commands.clean_content):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='wonka.png')


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def latte(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		await self.process_photofunia(ctx, 'all_effects', None,
																	'latte-art', img=url)



	@commands.command(aliases=["e2m", "emojim"])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def emojimosaic(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		try:
			x = await ctx.send("ok, processing")
			final = await self.generic_api("emoji_mosaic", get_images[0])
			await ctx.send(file=final, filename="emoji_mosaic.png")
		finally:
			await ctx.delete(x, error=False)


	@commands.command(aliases=["e2m2", "fe2m"])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def emojimosaic2(self, ctx, *, url:str=None):
		"""Use "-global" to ignore custom server emojis."""
		use_global = False
		if url:
			if url.startswith('-'):
				url = f" {url}"
			if ' -global' in url:
				use_global = True
				url = url.replace(' -global', '')

		get_images = await self.get_images(ctx, urls=url, scale=72, limit=2)
		if not get_images:
			return
		get_images, scale, scale_msg = get_images

		try:
			x = await ctx.send("ok, processing")
			image_urls = [get_images[0]]

			if not use_global and ctx.guild is not None:
				emojis = await ctx.guild.fetch_emojis()
				image_urls += [
					f'https://cdn.discordapp.com/emojis/{e.id}.png'
					for e in emojis
				]

			final = await self.f_api("e2m", *image_urls, text=scale or 64)
			await ctx.send(content=scale_msg, file=final, filename="emoji_mosaic2.png")
		finally:
			await ctx.delete(x, error=False)



	@commands.command(aliases=["airpod"])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def airpods(self, ctx, *, text:commands.clean_content):
		text = quote(text[:19])
		url = f"https://www.apple.com/shop/preview/engrave/PV7N2AM/A?th={text}&s=1"
		img = await self.bytes_download(url)
		await ctx.send(file=img, filename="airpods.png")

	@commands.command(aliases=["propods", "airpod2", "airpodspro"])
	@commands.cooldown(1, 3, commands.BucketType.guild)
	async def airpods2(self, ctx, *, text:commands.clean_content):
		text = quote(text[:22])
		url = f"https://www.apple.com/shop/preview/engrave/PWP22AM/A?th={text}&s=1"
		img = await self.bytes_download(url)
		await ctx.send(file=img, filename="airpodspro.png")


	@commands.command(aliases=["thonk"])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def thonkify(self, ctx, *, text:commands.clean_content):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='thonkify.png')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def neon(self, ctx, *, text:commands.clean_content):
		payload = FormData()
		split = text.split('|', maxsplit=1)
		if len(split) == 1 and len(split[0]) > 20:
			split.append(split[0][20:])
			# We trim at 20 chars down below
		key = "text"
		for idx, val in enumerate(split):
			if idx > 0:
				key += "2"
			payload.add_field(key, val[:20])
		await self.process_photofunia(ctx, 'all_effects', payload,
																	'neon-writing')


	@commands.command()
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def logout(self, ctx, *, text:commands.clean_content):
		final = await self.f_api(ctx.command.name, text=text)
		await ctx.send(file=final, filename='logout.png')


	@commands.command(aliases=["gcrystal", "gcrystallize"])
	@commands.cooldown(2, 5, commands.BucketType.guild)
	async def gifcrystallize(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		final = await self.f_api("magik_script", get_images[0], text="gcrystallize")
		await ctx.send(file=final, filename='gcrystallize.gif')


	async def do_quadart(self, ctx, url, box=False):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		try:
			x = await ctx.send("ok, processing")
			final = await self.generic_api(
				"quadart", get_images[0],
				draw_type='box' if box else 'circle'
			)
			await ctx.send(file=final, filename="quadart.png")
		finally:
			await ctx.delete(x, error=False)

	@commands.group(aliases=["quad"], invoke_without_command=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def quadart(self, ctx, *, url:str=None):
		await self.do_quadart(ctx, url)

	@quadart.command(name='box', aliases=["boxes"])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def quadart_box(self, ctx, *, url:str=None):
		await self.do_quadart(ctx, url, box=True)


	@commands.command(aliases=['timesquare'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def nyc(self, ctx, *, url:str=None):
		get_images = await self.get_images(ctx, urls=url, limit=1)
		if not get_images:
			return
		url = get_images[0]
		await self.process_photofunia(ctx, 'all_effects', None,
																	'new-york-at-night', img=url)


	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def lego(self, ctx, *urls:str):
		get_images, scale, scale_msg = await self.get_images(ctx, urls=urls, limit=1, scale=41)
		if not get_images:
			return
		scale = max(scale, 4) if scale else 20
		final = await self.f_api("lego", get_images[0], text=scale)
		await ctx.send(file=final, filename="lego.png", content=scale_msg)


def setup(bot):
	bot.add_cog(Fun(bot))
