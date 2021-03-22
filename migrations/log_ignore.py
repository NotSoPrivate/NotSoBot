import pymysql
import datetime

connection = pymysql.connect(host='localhost',
                             user='discord',
                             password='q3cnvtvWIy62BQlx',
                             db='discord',
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)
cursor = connection.cursor()

cursor.execute('SELECT * FROM `logs`')
result = cursor.fetchall()

sql = 'INSERT INTO `logs_ignore` (`type`, `server`, `id`) VALUES (%s, %s, %s)'
count = 0
for r in result:
  try:
    server, ignore_users, avatar_ignore = r['server'], r['ignore_users'], r['avatar_ignore']
    if ignore_users:
      for user in ignore_users.split(', '):
        cursor.execute(sql, (False, server, int(user)))
    if avatar_ignore:
      for user in avatar_ignore.split(', '):
        cursor.execute(sql, (True, server, int(user)))
    connection.commit()
  finally:
    count += 1
print('done', count)
