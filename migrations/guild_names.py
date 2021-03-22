from datetime import datetime

import pymysql

connection = pymysql.connect(host='192.168.15.16',
														 port=3307,
														 user='discord',
														 password='q3cnvtvWIy62BQlx',
														 db='discord',
														 charset='utf8mb4',
														 cursorclass=pymysql.cursors.DictCursor)
cursor = connection.cursor()

cursor.execute('SELECT * FROM `guild_names`')
result = cursor.fetchall()

# 04-01-2017|11:14 (EST)

sql = "INSERT INTO `guild_names2` (`guild`, `name`, `time`) VALUES (%s, %s, %s)"
for r in result:
	t = datetime.strptime(r['time'], "%m-%d-%Y|%I:%M (EST)")
	cursor.execute(sql, (r['guild'], r['name'], t))
	print('inserted', r)

connection.commit()
print('done - commited')
