import random
from urllib.parse import quote
from xml.etree import ElementTree

from discord.ext import commands
from mods.cog import Cog
from utils import checks


class Nsfw(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.bytes_download = bot.bytes_download
		self.get_json = bot.get_json
		self.get_text = bot.get_text

	async def banned_tags(self, ctx, search):
		if ctx.guild is None:
			return False
		q = await self.cursor.execute(f"SELECT * FROM `banned_nsfw_tags` WHERE guild={ctx.guild.id}")
		result = await q.fetchall()
		if not result:
			return False
		tags = [x['tag'].lower() for x in result]
		found = [t for t in tags if t in map(str.lower, search)]
		if found:
			return await ctx.send('\N{NO ENTRY} Your search included banned tag(s): `{0}`'.format(', '.join(found)))
		return False

	@commands.group(aliases=['bannsfwtag', 'bannsfwsearch', 'nsfwban'], invoke_without_command=True)
	@commands.guild_only()
	@checks.mod_or_perm(manage_messages=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def bantag(self, ctx, *tags:str):
		"""Ban a string/tag from being searched with nsfw commands"""
		if not tags:
			return await ctx.send("\N{WARNING SIGN} Please input tag(s) to ban.")
		tags = tags[:20]
		sql = 'INSERT INTO `banned_nsfw_tags` (`guild`, `tag`) VALUES (%s, %s)'
		for tag in tags:
			await self.cursor.execute(sql, (ctx.guild.id, tag))
		await ctx.send('\N{WHITE HEAVY CHECK MARK} Banned (**{0}**) tags: `{1}`.'.format(len(tags), ', '.join(tags)))

	@bantag.command(name='list', invoke_without_command=True)
	@commands.guild_only()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def bantag_list(self, ctx):
		"""List all banned tags"""
		sql = 'SELECT * FROM `banned_nsfw_tags` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send('\N{NO ENTRY} `Guild does not have any tags banned for nsfw commands!`')
		tags = [x['tag'] for x in result]
		await ctx.send('\N{WHITE HEAVY CHECK MARK} Banned NSFW Tags:\n`{0}`'.format(', '.join(tags)))

	@bantag.group(name='remove', invoke_without_command=True, aliases=['delete', 'unban'])
	@commands.guild_only()
	@checks.mod_or_perm(manage_messages=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def bantag_remove(self, ctx, *tags:str):
		"""Remove a banned tag"""
		tags = tags[:20]
		sql = "DELETE FROM `banned_nsfw_tags` WHERE guild=%s AND tag=%s"
		removed = False
		for tag in tags:
			check = "SELECT * FROM `banned_nsfw_tags` WHERE guild=%s AND tag=%s"
			q = await self.cursor.execute(check, (ctx.guild.id, tag))
			result = await q.fetchall()
			if result:
				await self.cursor.execute(sql, (ctx.guild.id, tag))
				if not removed:
					removed = True
		if removed:
			await ctx.send(
				"\N{WHITE HEAVY CHECK MARK} Removed tag(s) `{0}` from the ban list".format(', '.join(tags)) +
				", tags not included are not banned."
			)
		else:
			await ctx.send("\N{WARNING SIGN} None of those tags are banned.")

	@bantag_remove.command(name='all', invoke_without_command=True)
	@commands.guild_only()
	@checks.mod_or_perm(manage_messages=True)
	@commands.cooldown(1, 5, commands.BucketType.guild)
	async def bantag_remove_all(self, ctx):
		sql = 'DELETE FROM `banned_nsfw_tags` WHERE guild={0}'
		sql = sql.format(ctx.guild.id)
		check = 'SELECT * FROM `banned_nsfw_tags` WHERE guild={0}'
		check = check.format(ctx.guild.id)
		q = await self.cursor.execute(check)
		result = await q.fetchall()
		if not result:
			return await ctx.send('\N{NO ENTRY} `Guild does not have any tags banned for nsfw commands!`')
		await self.cursor.execute(sql)
		await ctx.send('\N{WHITE HEAVY CHECK MARK} Removed `all` banned tags.')

	@commands.command(aliases=['e6'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.nsfw()
	async def e621(self, ctx, *search:str):
		if not search:
			return await ctx.send("\N{WARNING SIGN} Please input something to search.")
		if len(search) > 6:
			return await ctx.send("Search limit exceeded (> 6).")
		if await self.banned_tags(ctx, search):
			return
		posts = await self.get_json(
			"https://beta.notsobot.com/api/search/e621?query={0}".format('%20'.join(search))
		)
		try:
			image = random.choice(posts)
			url = image['url']
			score = str(image['score']['total'])
			await ctx.send('`Score: {0}` {1}'.format(score, url))
		except IndexError:
			await ctx.send("\N{WARNING SIGN} `No results found on` <https://e621.net>")

	@commands.command(aliases=['r34'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.nsfw()
	async def rule34(self, ctx, *search:str):
		if not search:
			return await ctx.send("\N{WARNING SIGN} Please input something to search.")
		if await self.banned_tags(ctx, search):
			return
		url = "https://rule34.xxx/index.php?page=dapi&s=post&q=index&tags={0}".format('%20'.join(search))
		txt = await self.get_text(url)
		try:
			index = ElementTree.fromstring(txt)
			assert len(index) != 0
		except:
			return await ctx.send("\N{WARNING SIGN} `No results found on` <http://rule34.xxx>")
		image = random.choice(index)
		score = image.attrib['score']
		url = image.attrib["file_url"]
		if url.startswith('//'):
			url = f'http:{url}'
		_id = image.attrib["id"]
		if url.endswith(("swf", "webm")):
			await ctx.send("`Score: {0}` <http://rule34.xxx/index.php?page=post&s=view&id={1}> (Video)".format(score, _id))
		else:
			await ctx.send("`Score: {0}` <http://rule34.xxx/index.php?page=post&s=view&id={1}>\n{2}".format(score, _id, url))

	@commands.command(aliases=['r34p', 'rule34paheal', 'pahe'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.nsfw()
	async def paheal(self, ctx, *search:str):
		if not search:
			return await ctx.send("\N{WARNING SIGN} Please input something to search.")
		if await self.banned_tags(ctx, search):
			return
		url = "http://rule34.paheal.net/api/danbooru/find_posts?tags={0}".format('%20'.join(search))
		txt = await self.get_text(url)
		try:
			index = ElementTree.fromstring(txt)
			assert len(index) != 0
		except:
			return await ctx.send("\N{WARNING SIGN} `No results found on` <http://rule34.paheal.net>")
		image = random.choice(index)
		score = image.attrib['score']
		url = image.attrib["file_url"]
		if url.startswith('//'):
			url = f'http:{url}'
		_id = image.attrib["id"]
		if url.endswith(("swf", "webm")):
			await ctx.send("`Score: {0}` <http://rule34.paheal.net/post/view/{1}> (Video)".format(score, _id))
		else:
			await ctx.send("`Score: {0}` <http://rule34.paheal.net/post/view/{1}>\n{2}".format(score, _id, url))

	@commands.command()
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.nsfw()
	async def yande(self, ctx, *search:str):
		if not search:
			return await ctx.send("\N{WARNING SIGN} Please input something to search.")
		if await self.banned_tags(ctx, search):
			return
		url = "https://yande.re/post.json?tags={0}".format("+".join(search))
		load = await self.get_json(url)
		if not load:
			return await ctx.send("\N{WARNING SIGN} `No results found on` <https://yande.re>")
		load = random.choice(load)
		score = str(load['score'])
		await ctx.send('`Score: {0}` <https://yande.re/post/show/{1}>\n{2}'.format(score, load['id'], load['jpeg_url']))

	@commands.command(aliases=['xb'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.nsfw()
	async def xbooru(self, ctx, *search:str):
		if not search:
			return await ctx.send("\N{WARNING SIGN} Please input something to search.")
		if await self.banned_tags(ctx, search):
			return
		url = "http://xbooru.com/index.php?page=dapi&s=post&q=index&tags={0}".format('%20'.join(search))
		txt = await self.get_text(url)
		try:
			index = ElementTree.fromstring(txt)
			assert len(index) != 0
		except:
			return await ctx.send('\N{WARNING SIGN} `No results found on` <http://xbooru.com>')
		image = index[random.randrange(len(index))]
		score = str(image.attrib['score'])
		url = image.attrib["file_url"]
		if url.endswith(("swf", "webm")):
			await ctx.send("`Score: {0}` <http://xbooru.com/index.php?page=post&s=view&id={1}> (Video)".format(score, image.attrib["id"]))
		else:
			await ctx.send('`Score: {0}` <http://xbooru.com/index.php?page=post&s=view&id={1}>\n{2}'.format(score, image.attrib['id'], url))

	@commands.command(aliases=['gb', 'gel'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.nsfw()
	async def gelbooru(self, ctx, *search:str):
		if not search:
			return await ctx.send("\N{WARNING SIGN} Please input something to search.")
		if await self.banned_tags(ctx, search):
			return
		url = "http://gelbooru.com/index.php?page=dapi&s=post&q=index&tags={0}".format('%20'.join(search))
		txt = await self.get_text(url)
		try:
			index = ElementTree.fromstring(txt)
			assert len(index) != 0
		except:
			return await ctx.send('\N{WARNING SIGN} `No results found on` <http://gelbooru.com>')
		image = index[random.randrange(len(index))]
		score = str(image.attrib['score'])
		url = image.attrib["file_url"]
		if url.endswith(("swf", "webm")):
			await ctx.send("`Score: {0}` <http://gelbooru.com/index.php?page=post&s=view&id={1}> (Video)".format(score, image.attrib["id"]))
		else:
			await ctx.send('`Score: {0}` <http://gelbooru.com/index.php?page=post&s=view&id={1}>\n{2}'.format(score, image.attrib['id'], url))

	@commands.command(aliases=['ph', 'porn'])
	@commands.cooldown(1, 5, commands.BucketType.guild)
	@checks.nsfw()
	async def pornhub(self, ctx, *, search:str):
		if await self.banned_tags(ctx, search):
			return
		api = 'https://www.pornhub.com/webmasters/search?search={0}'.format(quote(search))
		load = await self.get_json(api, content_type=None)
		if 'videos' not in load:
			return await ctx.send('\N{WARNING SIGN} `No results found on` <http://pornhub.com>')
		load = random.choice(load['videos'][:3])
		ps = load['pornstars']
		await ctx.send('**{0}**{1}\n{2}'.format(load['title'], '\nPornstars: `{0}`'.format(', '.join([x['pornstar_name'] for x in ps])) if ps else '', 'http://www.pornhub.com/view_video.php?viewkey={0}'.format(load['video_id'])))

def setup(bot):
	bot.add_cog(Nsfw(bot))
