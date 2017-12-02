import pymysql as sql

db = sql.connect('localhost', '', 'david', 'mmeds_db')

cursor = db.cursor()

cursor.execute('SELECT VERSION()')

data = cursor.fetchone()

print('Database version : %s' % data)

db.close()
