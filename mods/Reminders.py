import pymysql.err

from datetime import datetime, timedelta
from time import time as now

from discord.ext import commands, tasks
from mods.cog import Cog
from utils.paginator import CannotPaginate, Pages
from utils.time import UserFriendlyTime, human_timedelta

class Reminders(Cog):
	def __init__(self, bot):
		super().__init__(bot)
		self.truncate = bot.funcs.truncate
		if 0 in bot.shard_ids:
			self._remind_task.add_exception_type(pymysql.err.InternalError)
			self._remind_task.add_exception_type(pymysql.err.OperationalError)
			self._remind_task.start()


	def cog_unload(self):
		if 0 in self.bot.shard_ids:
			self._remind_task.cancel()

	async def get_reminders(self):
		sql = "SELECT * FROM `reminders` WHERE `time` < UNIX_TIMESTAMP(DATE_ADD(NOW(), INTERVAL 30 DAY))"
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return False
		result = [dict(s.items()) for s in result]
		reminds = {}
		for s in result:
			u = s['user']
			t = s['time']
			m = s['message']
			mid = s.get('message_id', None)
			c = s.get('channel', None)
			g = s.get('guild', None)
			if u in reminds:
				if t in reminds[u]:
					continue
				# TODO: refactor this one day
				reminds[u][0].append(t)
				reminds[u][1].append(m)
				reminds[u][2].append(mid)
				reminds[u][3].append(c)
				reminds[u][4].append(g)
			else:
				reminds[u] = [[t], [m], [mid], [c], [g]]
		return reminds

	@staticmethod
	def remind_due(when):
		return int(now()) >= when

	async def remove_reminder(self, user:int, time:int):
		sql = f'DELETE FROM `reminders` WHERE user={user} AND time={time}'
		await self.cursor.execute(sql)

	@tasks.loop(seconds=4.5)
	async def _remind_task(self):
		reminders = await self.get_reminders()
		if reminders is False:
			return
		for user in reminders:
			r = reminders[user]
			for t in r[0]:
				is_due = self.remind_due(int(t))
				if is_due is False:
					continue
				index = r[0].index(t)
				message = r[1][index]
				message_id = r[2][index]
				if message_id: # backwards compat
					channel = r[3][index]
					guild = r[4][index]
				u = self.bot.get_user(user)
				if u is None:
					u = await self.bot.fetch_user(user)
				base = "\N{ALARM CLOCK} Reminder: "
				try:
					msg = f"{base}`"
					if message is None:
						msg += "time is up!`"
					else:
						msg += f"{message}`."
					if message_id:
						msg += f"\n\n<https://discordapp.com/channels/{guild}/{channel}/{message_id}>"
					await self.truncate(u, msg)
				except:
					pass
				await self.remove_reminder(user, t)

	@commands.group(aliases=['remindme'], invoke_without_command=True)
	@commands.cooldown(2, 5, commands.BucketType.user)
	async def remind(self, ctx, *, when:UserFriendlyTime(commands.clean_content, default='\u2026')=None):
		if not when:
			return await ctx.send(
				'\N{WARNING SIGN} `Invalid Time Format`\n**Example:** `1h2m` (1 hour, 2 minutes)'
			)
		time = when.dt
		text = when.arg
		if (datetime.now() + timedelta(days=760)) < time:
			return await ctx.send("\N{WARNING SIGN} no need, you won't live that long (> 2 years).")

		sql = 'INSERT INTO `reminders` (`user`, `time`, `message`, `channel`, `message_id`, `guild`) ' \
					'VALUES (%s, %s, %s, %s, %s, %s)'

		epoch = int(time.strftime("%s"))
		gid = getattr(ctx.guild, 'id', '@me')
		data = (
			ctx.author.id,
			epoch, text or None,
			ctx.channel.id,
			ctx.message.id,
			gid
		)
		await self.cursor.execute(sql, data)

		await ctx.send(f'\N{WHITE HEAVY CHECK MARK} Reminder set for `{human_timedelta(time)}` from now.')

	@remind.command(name='list', invoke_without_command=True)
	@commands.cooldown(1, 7, commands.BucketType.user)
	async def remind_list(self, ctx):
		sql = 'SELECT * FROM `reminders` WHERE user={0}'.format(ctx.author.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send("\N{NO ENTRY} You don't have any reminders set!")
		try:
			entries = [
				f"**__{human_timedelta(datetime.fromtimestamp(x['time']))}__**" \
				f"\n{x['message'] or ''}" \
				for x in result
			]
			p = Pages(ctx, entries=entries, per_page=8, show_zero=False)
			p.embed.title = 'Reminders'
			p.embed.color = self.bot.funcs.get_color()()
			p.embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url_as())
			await p.paginate()
		except CannotPaginate:
			reminders = []
			count = 0
			for reminder in result:
				created_at = human_timedelta(datetime.fromtimestamp(reminder['time']))
				if reminder['message'] is not None:
					reminders.append('**{0}.** __{2}__: `{1}`'.format(count, reminder['message'], created_at))
				else:
					reminders.append('**{0}.** __{1}__'.format(count, created_at))
				count += 1
			await self.truncate(ctx.channel, '**Reminders**\n{0}'.format('\n'.join(reminders)))

	@remind.group(name='remove', invoke_without_command=True, aliases=['delete'])
	async def remind_remove(self, ctx, *ids:int):
		if not ids:
			return await ctx.send('\N{NO ENTRY} `Please input reminder id(s) to remove.`')
		sql = 'SELECT * FROM `reminders` WHERE user={0}'.format(ctx.author.id)
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send("\N{NO ENTRY} You don't have any reminders set!")
		sql = 'DELETE FROM `reminders` WHERE user={0} AND id={1}'
		ids = list(ids)
		for x in ids:
			try:
				sql = sql.format(ctx.author.id, result[int(x)-1]['id'])
			except:
				if len(ids) == 1:
					return await ctx.send(f'\N{WARNING SIGN} Reminder **#{x}** does not exist!')
				ids.remove(x)
				continue
			else:
				await self.cursor.execute(sql)
		if not ids:
			await ctx.send(
				'\N{WARNING SIGN} No valid reminder ids were given, use `reminder list` to see your reminders.'
			)
		else:
			await ctx.send(
				'\N{NEGATIVE SQUARED CROSS MARK} Removed reminder{0} **#{1}**'.format(
					's' if len(ids) > 1 else '',
					', '.join(map(str, ids))
				)
			)

	@remind_remove.command(name='all', invoke_without_command=True)
	@commands.cooldown(1, 10, commands.BucketType.user)
	async def remind_remove_all(self, ctx):
		sql = f'SELECT * FROM `reminders` WHERE user={ctx.author.id}'
		q = await self.cursor.execute(sql)
		result = await q.fetchall()
		if not result:
			return await ctx.send("\N{NO ENTRY} You don't have any reminders set!")
		sql = f'DELETE FROM `reminders` WHERE user={ctx.author.id}'
		await self.cursor.execute(sql)
		await ctx.send('\N{NEGATIVE SQUARED CROSS MARK} `Removed all reminders.`')

def setup(bot):
	if not bot.self_bot:
		bot.add_cog(Reminders(bot))
