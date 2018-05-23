import pymysql as pms

db = pms.connect('localhost', 'root', '', 'mmeds', local_infile=True)

c = db.cursor()
c.execute('SHOW TABLES;')

ables = ['session', 'user', 'security_token']


def func(x):
    return 'has' not in x and 'protected' not in x and x not in ables


tables = list(filter(func, [x[0] for x in c.fetchall()]))

print(tables)


drop_sql = 'DROP VIEW IF EXISTS `mmeds`.`protected_{}`;\n'
view_sql = 'CREATE\nSQL SECURITY DEFINER\nVIEW protected_{} AS\nSELECT cc.* FROM `mmeds`.`{}` cc WHERE owner_check(cc.user_id)\nWITH CHECK OPTION;\n\n'
grant_sql = "GRANT SELECT ON TABLE `mmeds`.`protected_{}` TO 'mmeds_user'@'%';\n\n"
with open('/home/david/Work/mmeds-meta/DB/security_view.sql', 'w') as f:
    for table in tables:
        f.write(drop_sql.format(table))
        f.write(view_sql.format(table, table))
        f.write(grant_sql.format(table))
