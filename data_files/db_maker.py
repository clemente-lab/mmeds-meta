from mmeds.config import PROTECTED_TABLES, PUBLIC_TABLES, SQL_DATABASE, HTML_DIR
SQL_USER_NAME = 'mmeds_user'
drop_sql = 'DROP VIEW IF EXISTS `{db}`.`protected_{table}`;\n'
view_sql = 'CREATE\nSQL SECURITY DEFINER\nVIEW `{db}`.`protected_{table}` AS\nSELECT cc.* FROM `{db}`.`{table}` cc WHERE `{db}`.`owner_check`(cc.user_id)\nWITH CHECK OPTION;\n\n'
grant_sql = "GRANT SELECT ON TABLE `{db}`.`protected_{table}` TO '{user}'@'%';\n\n"
public_sql = "GRANT SELECT ON TABLE `{db}`.`{table}` TO '{user}'@'%';\n\n"
with open(HTML_DIR.parent / 'sql/views.sql', 'w') as f:
    for table in PROTECTED_TABLES:
        f.write(drop_sql.format(db=SQL_DATABASE, table=table))
        f.write(view_sql.format(db=SQL_DATABASE, table=table))
        f.write(grant_sql.format(db=SQL_DATABASE, user=SQL_USER_NAME, table=table))

    for table in PUBLIC_TABLES:
        f.write(public_sql.format(db=SQL_DATABASE, table=table, user=SQL_USER_NAME))

