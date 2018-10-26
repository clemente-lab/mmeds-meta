from mmeds.config import PROTECTED_TABLES, PUBLIC_TABLES, SQL_DATABASE

drop_sql = 'DROP VIEW IF EXISTS `{}`.`protected_{}`;\n'
view_sql = 'CREATE\nSQL SECURITY DEFINER\nVIEW protected_{} AS\nSELECT cc.* FROM `{}`.`{}` cc WHERE owner_check(cc.user_id)\nWITH CHECK OPTION;\n\n'
grant_sql = "GRANT SELECT ON TABLE `{}`.`protected_{}` TO 'mmeds_user'@'%';\n\n"
public_sql = "GRANT SELECT ON TABLE `{}`.`{}` TO 'mmeds_user'@'%';\n\n"
with open('/home/david/Work/mmeds-meta/sql/views.sql', 'w') as f:
    for table in PROTECTED_TABLES:
        f.write(drop_sql.format(SQL_DATABASE, table))
        f.write(view_sql.format(SQL_DATABASE, table, table))
        f.write(grant_sql.format(SQL_DATABASE, table))

    for table in PUBLIC_TABLES:
        f.write(public_sql.format(SQL_DATABASE, table))
