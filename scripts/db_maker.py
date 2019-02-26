from mmeds.config import PROTECTED_TABLES, PUBLIC_TABLES
from mmeds.secrets import SQL_USER_NAME, SQL_DATABASE
from sys import argv


drop_sql = 'DROP VIEW IF EXISTS `{db}`.`protected_{table}`;\n'
view_sql = 'CREATE\nSQL SECURITY DEFINER\nVIEW `{db}`.`protected_{table}` AS\nSELECT cc.* FROM `{db}`.`{table}` ' +\
            'cc WHERE `{db}`.`owner_check`(cc.user_id)\nWITH CHECK OPTION;\n\n'
grant_sql = "GRANT SELECT ON TABLE `{db}`.`protected_{table}` TO '{user}'@'%';\n\n"
public_sql = "GRANT SELECT ON TABLE `{db}`.`{table}` TO '{user}'@'%';\n\n"
if len(argv) < 2:
    view_file = 'sql/views.sql'
else:
    view_file = argv[1]

with open(view_file, 'w') as f:
    for table in PROTECTED_TABLES:
        f.write(drop_sql.format(db=SQL_DATABASE, table=table))
        f.write(view_sql.format(db=SQL_DATABASE, table=table))
        f.write(grant_sql.format(db=SQL_DATABASE, user=SQL_USER_NAME, table=table))

    for table in PUBLIC_TABLES:
        f.write(public_sql.format(db=SQL_DATABASE, table=table, user=SQL_USER_NAME))
