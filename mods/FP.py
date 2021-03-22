import re
import cfscrape
from discord.ext import commands
from discord import Embed
from mods.cog import Cog
from utils import checks
from lxml import etree

class FP(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.url_regex = re.compile(r'(https?:\/\/(?:www\.|(?!www))facepunch\.com/showthread\.php\?t=(\d*))(&p=(\d*))?', re.I)
		self.get_text = bot.get_text
		self.scraper = cfscrape.create_scraper()
		self.cache = {}
		self.get_deep_text = bot.funcs.get_deep_text

	def cog_unload(self):
		self.scraper.close()

	def parse_fp(self, body, post_id=None):
		e = Embed()
		root = etree.fromstring(body, etree.HTMLParser(collect_ids=False))
		if post_id:
			pass
		else:
			title = root.find('.//div[@id="lastelement"]/span').text
			posts = root.find('.//ol[@class="posts"]')
			op_node = posts.find('.//li')
			age_node = op_node.find('.//div[@class="posthead"]/span[@class="postdate old"]/span')
			age = f"{age_node.get('title')} ({age_node.text})"
			op_info = op_node.find('.//div[@class="postdetails"]')
			op_url = f"https://facepunch.com/{op_info.find('.//div/a').get('href')}"
			op_name = op_info.find('.//div/div/a/strong/font')
			if op_name is None:
				op_name = op_info.find('.//div/div/a/span').text
			else:
				op_name = op_name.text
			op_data = op_info.find('.//div[@id="userdata"]')
			avatar = op_data.find('.//a/img')
			if avatar is not None:
				op_avatar = f"https://facepunch.com/{avatar.get('src')}"
				e.set_thumbnail(url=op_avatar)
			op_stats = op_data.find('.//div')
			op_join = op_stats.text.strip()
			op_posts = op_stats.getchildren()[0].tail.strip().split()
			post_count = root.find('.//span[@class="selected"]/a')
			if post_count is None:
				post_count = len(posts.findall('.//li'))
			else:
				post_count = post_count.get('title').split()[-1]
			post_snip = '{0}...'.format(self.get_deep_text(root.find('.//div[@class="content"]/div/blockquote')).strip()[:200])
			e.color = 0x738bd7
			e.title = title
			e.description = f"**OP**: [{op_name}]({op_url})\n**OP Posts**: `{op_posts[0]}`\n**OP Join**: __{op_join}__"
			e.add_field(name='OP Snippet', value=post_snip, inline=True)
			e.set_footer(text=f'{post_count} posts | {age}')
		return e

	async def check(self, guild):
		sql = 'SELECT guild FROM `fp_embed` WHERE guild=%s'
		q = await self.cursor.execute(sql, (guild,))
		return bool(await q.fetchone())

	@commands.command()
	@commands.guild_only()
	@checks.admin_or_perm(manage_guild=True)
	async def fpembed(self, ctx):
		guild = ctx.guild.id
		check = await self.check(guild)
		if check:
			await self.cursor.execute('DELETE FROM `fp_embed` WHERE guild=%s', (guild,))
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Disabled Facepunch embeds.')
		else:
			await self.cursor.execute('INSERT INTO `fp_embed` (`guild`) VALUES (%s)', (guild,))
			await ctx.send('\N{WHITE HEAVY CHECK MARK} Enabled Facepunch embeds.')

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None or message.author.bot:
			return
		check = await self.check(message.guild.id)
		if not check:
			return
		match = self.url_regex.findall(message.clean_content)
		if not match:
			return
		urls = list(set(match))[:2]
		for url, thread_id, _, post_id in urls:
			thread_id = int(thread_id)
			if thread_id in self.cache:
				e = self.cache[thread_id]
			else:
				try:
					body = await self.scraper.make_request('get', url)
				except:
					continue
				e = self.parse_fp(body, post_id)
				e.url = url
				self.cache[thread_id] = e
			await message.channel.send(embed=e)

def setup(bot):
	if not bot.self_bot:
		bot.add_cog(FP(bot))