import asyncio
import re
from ast import literal_eval
from datetime import datetime

from discord.ext import commands

from aiomysql import create_pool, DictCursor
from pymysql.converters import encoders, escape_item, escape_string
from pymysql.err import OperationalError


class MySQLAdapter(commands.Cog):
	def __init__(self, bot):
		bot.mysql = self
		self.bot = bot
		self.loaded = asyncio.Event()
		self.ignore = (
			'messages',
			'command_logs',
			'names',
			'guild_names',
			'stats',
			'tags',
			'reminders',
			'test',
			'ratings',
			'feedback',
			'markov',
			'compliment'
		)
		self.rpc_ignore = (
			'raids',
			'muted',
			'muted2'
		)
		self.data = {}
		self.indexes = {}
		self.defaults = {}
		self.insert_regex = re.compile(r'INSERT INTO `(.*)` \((.*)\) VALUES (.*)', re.I|re.S)
		self.select_regex = re.compile(r'SELECT (.*) FROM `(.*)` ?(?:WHERE)?.?(.*)', re.I|re.S)
		self.delete_regex = re.compile(r'DELETE FROM `(.*)` WHERE (.*)', re.I|re.S)
		self.update_regex = re.compile(r'UPDATE `(.*)` SET (.*)', re.I|re.S)
		self.set_regex = re.compile(r'(.*)=(.*)', re.S)
		self.set2_regex = re.compile(r'(.*)=(.*), (.*)=(.*)', re.S)
		self.order_regex = re.compile(r'ORDER BY (.*) (DESC|ASC)', re.S)
		self.limit_regex = re.compile(r'LIMIT (\d*)$', re.I)
		self._patch()
		bot.loop.create_task(self.connect())


	def cog_unload(self):
		self.loaded.clear()
		self.close_mysql()
		self.bot.loop.create_task(self.pool.wait_closed())

	@commands.Cog.listener()
	async def on_rpc_receive(self, data):
		if int(data['id']) == self.bot.rpc.get_id():
			return
		payload = data.get('payload')
		if payload:
			cmd = payload.get('command')
			if cmd == 'update_data':
				await self.loaded.wait()
				action = payload['action']
				if action == 'insert':
					table, data = payload['data']
					if not self.shard_check(data):
						if "time" in data:
							data['time'] = datetime.strptime(data['time'], '%Y-%m-%d %H:%M:%S.%f')
						self.data[table].append(data)
				else:
					args = payload['args']
					await getattr(self, action)(payload['sql'], tuple(args) if args else None, local=True)

	def get_shard(self, server_id:int):
		return (server_id >> 22) % self.bot.shard_count

	def shard_check(self, row):
		return 'server' in row and row['server'] \
						and self.get_shard(row['server']) not in self.bot.shard_ids

	async def process_table(self, table):
		self.data[table] = []
		self.indexes[table] = []
		self.defaults[table] = {}
		q = await self._execute(f'SELECT * FROM `{table}`', fetch=True)
		data = await q.fetchall()
		for row in data:
			row = dict(row)
			if self.shard_check(row):
				continue
			self.data[table].append(row)
		q = await self._execute(f'SHOW INDEX FROM `{table}`', fetch=True)
		indexes = await q.fetchall()
		for index in indexes:
			if index['Non_unique']:
				continue
			t = self.indexes[table]
			column = index['Column_name']
			if column not in t:
				t.append(column)
		# TODO: implement more defaults
		q = await self._execute(f'SHOW COLUMNS FROM `{table}`', fetch=True)
		defs = await q.fetchall()
		for d in defs:
			dic = self.defaults[table]
			if d['Null'] == "YES":
				dic[d['Field']] = d['Default']

	async def get_data(self):
		q = await self._execute('SHOW TABLES', fetch=True)
		tables = await q.fetchall()
		db = list(tables[0].keys())[0]
		for table in tables:
			table = table[db]
			if table in self.ignore:
				continue
			await self.process_table(table)

	async def connect(self):
		if self.bot.dev_mode:
			db = 'discord_dev'
		elif self.bot.self_bot:
			db = 'discord_self'
		else:
			db = 'discord'
		self.pool = await create_pool(host='192.168.15.16', port=3307, db=db, user='discord',
																			password='q3cnvtvWIy62BQlx', charset='utf8mb4',
																			use_unicode=True, loop=self.bot.loop, maxsize=2)
		await self.get_data()
		self.loaded.set()

	def close_mysql(self):
		self.pool.close()

	def _patch(self):
		from utils.funcs import Object
		self.cursor = Object()
		self.cursor.execute = self.execute
		#PyMYSQL Escape Patch
		encoders[ord(':')] = '\:'

	async def execute(self, sql, args=None):
		await self.loaded.wait()
		sql_type = sql.split(maxsplit=1)[0].lower()
		try:
			return await getattr(self, sql_type)(sql, args)
		except AttributeError:
			return await self._execute(sql, args)

	async def _execute(self, sql, args=None, commit=False, fetch=False):
		try:
			async with self.pool.acquire() as conn:
				try:
					cursor = await conn.cursor(DictCursor)
					if args is not None:
						r = await cursor.execute(sql, args)
					else:
						r = await cursor.execute(sql)
					if commit:
						await conn.commit()
					elif fetch:
						r = Results(await cursor.fetchall())
					return r
				except (OperationalError, RuntimeError):
					if self.loaded.is_set():
						self.loaded.clear()
						await conn.ping()
						self.loaded.set()
				finally:
					await cursor.close()
		except (OperationalError):
			# :(
			return

	async def publish(self, data):
		await self.bot.rpc.publish(data, None, default_enc=str)

	async def increment_check(self, table, data):
		table_data = self.data[table]
		if table_data:
			first = table_data[-1]
			if 'id' in first:
				q = await self._execute(
					'SHOW TABLE STATUS WHERE name=%s', (table),
					fetch=True
				)
				r = await q.fetchone()
				data['id'] = r['Auto_increment']
			if 'time' in first:
				# close enough
				data['time'] = datetime.now()
		
		defs = self.defaults[table]
		if defs:
			for column in defs:
				if column not in data:
					data[column] = defs[column]

		return data

	def parse_data(self, columns, data):
		columns = columns.replace('`', '').replace(' ' ,'').split(',')
		data = literal_eval(data)
		return dict(zip(columns, data if isinstance(data, tuple) else (data,)))

	async def insert(self, sql, args, local=False):
		match = self.insert_regex.findall(sql % self.escape_args(args) if args else sql)[0]
		table = match[0]
		check = table in self.data
		if check:
			data = await self.increment_check(table, self.parse_data(match[1], match[2]))
			self.data[table].append(data)
		if not local:
			await self._execute(sql, args, commit=True)
			if check and table not in self.rpc_ignore:
				await self.publish({
					'command': 'update_data',
					'action': 'insert',
					'data': [
						table,
						data
					]
				})

	def conditions_parser(self, checks):
		c = {}
		split = checks.split(' AND ')
		for check in split:
			s = check.split('=')
			if len(s) > 1:
				column = s[0]
				value = check[check.index('=')+1:]
			else:
				if 'IS NULL' in s[0]:
					column = s[0].split(' IS ')[0]
					value = False
				else:
					column, value = s[0], True
			if isinstance(value, str):
				try:
					value = int(value) if value.isdigit() else value
				except ValueError:
					pass
			c[column] = value
		return c

	def order_parser(self, sql):
		match = self.order_regex.findall(sql)
		if match:
			table, order = match[0]
			return table, order == 'DESC'
		return False

	def default_value_check(self, table, columns):
		data = self.data[table]
		if data:
			if columns is False:
				columns = data[0].keys()
			return not all(x in data[-1] for x in columns)

	@staticmethod
	def run_checks(row, checks):
		for column in checks:
			if column in row and row[column] != checks[column]:
				return True
		return False

	async def select(self, sql, args):
		formated_sql = sql % args if args else sql
		limit_match = self.limit_regex.findall(formated_sql)
		if limit_match:
			limit = int(limit_match[0])
			formated_sql = formated_sql[:-7 - len(str(limit))]
		what, table, checks = self.select_regex.findall(formated_sql)[0]
		count = False
		if what == '*':
			what = False
		elif what.startswith('COUNT'):
			count = True
		else:
			what = what.split(',')
		table_check = table in self.data
		if not table_check or self.default_value_check(table, what):
			return await self._execute(sql, args, fetch=True)
		table_data = self.data[table]
		if checks:
			checks = self.conditions_parser(checks)
		order = self.order_parser(sql)
		if not checks and not what:
			data = table_data
		else:
			data = []
			for row in table_data:
				if self.run_checks(row, checks):
					continue
				if isinstance(what, list):
					new_row = row.copy()
					for c in row:
						if c not in what:
							new_row.pop(c)
					row = new_row
				data.append(row)
		if count:
			count_column = what[6:-1]
			if count_column == '*':
				count = len(data)
			else:
				c = count_column[1:-1]
				count = sum(x[c] for x in data if x[c])
			return Results([{f'COUNT({count_column})': count}])
		elif order:
			data = sorted(data, reverse=order[1], key=lambda x: x[order[0]])
		if limit_match:
			data = data[:limit]
		return Results(data)

	#TODO: support or checks
	async def delete(self, sql, args, local=False):
		table, checks = self.delete_regex.findall(sql % args if args else sql)[0]
		check = table in self.data
		if check:
			if checks:
				checks = self.conditions_parser(checks)
			data = self.data[table]
			for i, row in enumerate(data):
				if self.run_checks(row, checks):
					continue
				del data[i]
		if not local:
			await self._execute(sql, args, commit=True)
			if check and table not in self.rpc_ignore:
				await self.publish({
					'command': 'update_data',
					'action': 'delete',
					'sql': sql,
					'args': args
				})

	def update_parser(self, set_value):
		match = self.set2_regex.findall(set_value)
		if not match:
			match = self.set_regex.findall(set_value)[0]
		else:
			match = match[0]
		values = {}
		count = 0
		for value in match:
			if count % 2:
				column = match[count - 1]
				values[column] = value
			count += 1
		return values

	async def update(self, sql, args, local=False):
		match = self.update_regex.findall(sql % args if args else sql)[0]
		table = match[0]
		check = table in self.data
		if check:
			split = match[1].split(' WHERE ')
			set_value = split[0]
			if len(split) > 1:
				checks = self.conditions_parser(split[1])
			set_value = self.update_parser(set_value)
			data = self.data[table]
			for row in data:
				if self.run_checks(row, checks):
					continue
				for column in set_value:
					row[column] = set_value[column]
		if not local:
			await self._execute(sql, args, commit=True)

	async def replace(self, sql, args, local=False):
		sql2 = f'INSERT {sql[8:]}'
		match = self.insert_regex.findall(sql2 % self.escape_args(args) if args else sql2)[0]
		table = match[0]
		check = table in self.data
		if check:
			if table in self.indexes:
				data = self.parse_data(match[1], match[2])
				for column in data:
					if column in self.indexes:
						await self.delete(
							f'DELETE FROM `{table}` WHERE {column}={data[column]}',
							None, local=True
						)
			await self.insert(sql2, args, local=True)
		if not local:
			await self._execute(sql, args, commit=True)

	def escape_args(self, args):
		if isinstance(args, (tuple, list)):
			return tuple(self.escape(arg) for arg in args)
		return None

	@staticmethod
	def escape(obj, mapping=encoders):
		if isinstance(obj, str):
			return "'" + escape_string(obj) + "'"
		elif isinstance(obj, type(None)):
			return 'None'
		return escape_item(obj, 'utf8mb4', mapping=mapping)

class Results(list):
	async def fetchall(self):
		return self

	async def fetchone(self):
		if len(self) >= 1:
			return self[0]
		return []


def setup(bot):
	bot.add_cog(MySQLAdapter(bot))
