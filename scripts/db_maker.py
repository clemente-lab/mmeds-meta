from mmeds.config import PROTECTED_TABLES, PUBLIC_TABLES, ALL_TABLE_COLS, TABLE_ORDER
from mmeds.secrets import SQL_USER_NAME, SQL_DATABASE
from mmeds.util import quote_sql
from sys import argv


# Define the sql statments
drop_sql = 'DROP VIEW IF EXISTS {db}.{ptable};\n'
view_sql = 'CREATE\nSQL SECURITY DEFINER\nVIEW {db}.{ptable} AS\nSELECT cc.* FROM {db}.{table} ' +\
            'cc WHERE {db}.owner_check(cc.user_id)\nWITH CHECK OPTION;\n\n'
grant_sql = "GRANT SELECT ON TABLE {db}.{ptable} TO "
public_sql = "GRANT SELECT ON TABLE {db}.{table} TO "
user = '{user}@"%";\n\n'


def insert_null(table):
    sql = quote_sql('INSERT INTO {table} VALUES (', table=table)
    for i, column in enumerate(ALL_TABLE_COLS[table]):
            if 'id' in column:
                if i == 0:
                    sql += '1'
                else:
                    sql += ', 1'
            else:
                sql += ', NULL'
    sql += ');\n\n'
    return sql


# If given an argument write the script where specified
if len(argv) < 2:
    view_file = 'sql/views.sql'
else:
    view_file = argv[1]

# Write the sql rules for each table
with open(view_file, 'w') as f:

    # Users can access the views for protected tables
    for table in PROTECTED_TABLES:
        f.write(quote_sql(drop_sql, db=SQL_DATABASE, ptable='protected_{}'.format(table)))
        f.write(quote_sql(view_sql, db=SQL_DATABASE, table=table, ptable='protected_{}'.format(table)))
        f.write(quote_sql(grant_sql, db=SQL_DATABASE, table=table, ptable='protected_{}'.format(table)) +
                quote_sql(user, quote="'", user=SQL_USER_NAME, db=SQL_DATABASE))

    # They can access all the rows of public tables
    for table in PUBLIC_TABLES:
        f.write(quote_sql(public_sql, db=SQL_DATABASE, table=table) +
                quote_sql(user, quote="'", user=SQL_USER_NAME))

    for table in TABLE_ORDER:
        try:
            f.write(insert_null(table))
        # AdditionalMetaData and ICDCode don't exist in the database
        except KeyError as e:
            print(e)
