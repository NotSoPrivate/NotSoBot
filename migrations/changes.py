import pymysql
import datetime

connection = pymysql.connect(host='localhost',
														 user='discord',
														 password='q3cnvtvWIy62BQlx',
														 db='discord',
														 charset='utf8mb4',
														 cursorclass=pymysql.cursors.DictCursor)
cursor = connection.cursor()

cursor.execute('SELECT * FROM `names`')
result = cursor.fetchall()

# sql = 'INSERT INTO `new_names` (`user`, `server`, `name`, `nick`, `discrim`, `new_discrim`, `time`) VALUES (%s, %s, %s, %s, %s, %s, %s)'
# count = 0
# for r in result:
# 	try:
# 		user, name, nick, time, server, discrim = r
# 		if discrim:
# 			discrim, new_discrim = discrim.split(' => ')
# 			discrim = discrim.replace('`', '').replace('#', '')
# 			new_discrim = new_discrim.replace('`', '').replace('#', '')
# 		else:
# 			new_discrim = None
# 		if len(result) >= count:
# 			try:
# 				rr = result[count-1]
# 				if rr['name'] == r['name'] and rr['time'] == r['time']:
# 					continue
# 			except:
# 				pass
# 		nick = True if nick == '1' else False
# 		time = datetime.datetime.strptime(time, '%m-%d-%Y|%I:%M (EST)')
# 		name = name.replace('**Discriminator Change** ', '')
# 		cursor.execute(sql, (user, server, name, nick, discrim, new_discrim, time))
# 		connection.commit()
# 	finally:
# 		count += 1

sql = 'DELETE FROM `names` WHERE id=%s'
for count, r in enumerate(result):
	if count == 0:
		continue
	rr = result[count-1]
	if rr['name'] == r['name'] and rr['time'] >= (r['time'] - datetime.timedelta(minutes=1)) and rr['time'] <= (r['time'] + datetime.timedelta(minutes=1)):
		cursor.execute(sql, (r['id'],))
		connection.commit()
		print('removed', count, r)

print('done', count)
