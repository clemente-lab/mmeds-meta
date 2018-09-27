from mmeds.database import Database
from mmeds.authentication import add_user
from prettytable import PrettyTable, ALL
import mmeds.config as fig
import pymysql as pms
import pandas as pd
import random

# Checking whether or NOT a blank value or default value can be retrieved from the database.
# Validating each value if it is successfully saved to the database.
# Ensuring the data compatibility against old hardware or old versions of operating systems.
# Verifying the data in data tables can be modified and deleted
# Running data tests for all data files, including clip art, tutorials, templates, etc.


def format(text, header=None):
    """
    Applies PrettyTable HTML formatting to the provided string.
    """
    if header is not None:
        new_text = PrettyTable(header, border=True, hrules=ALL, vrules=ALL)
    else:
        new_text = PrettyTable(border=True, hrules=ALL, vrules=ALL)
    for line in text:
        new_text.add_row(list(map(str, line)))
    return new_text.get_html_string()


def build_sql(table, df, row, c):
    sql = 'DESCRIBE {}'.format(table)
    c.execute(sql)
    result = c.fetchall()
    all_cols = [res[0] for res in result]
    foreign_keys = list(filter(lambda x: '_has_' not in x,
                               list(filter(lambda x: '_id' in x,
                                           all_cols))))
    # Remove the table id for the row as
    # that doesn't matter for the test
    if 'user_id' in foreign_keys:
        del foreign_keys[foreign_keys.index('user_id')]
    columns = list(filter(lambda x: '_id' not in x, all_cols))
    if 'id' + table in columns:
        del columns[columns.index('id' + table)]
    sql = 'SELECT * FROM {} WHERE '.format(table)
    # Create an sql query to match the data from this row of the input file
    for i, column in enumerate(columns):
        value = df[table][column].iloc[row]
        if pd.isnull(value):
            value = 'NULL'
        if i == 0:
            sql += ' '
        else:
            sql += ' AND '
        # Add qoutes around string values
        if type(value) == str:
            sql += column + ' = "' + value + '"'
        # Otherwise check the absolute value of the difference is small
        # so that SQL won't fail to match floats
        else:
            sql += ' ABS(' + table + '.' + column + ' - ' + str(value) + ') <= 0.01'

    # Collect the matching foreign keys based on the infromation
    # in the current row of the data frame
    for fkey in foreign_keys:
        ftable = fkey.split('_id')[1]
        # Recursively build the sql call
        fsql = build_sql(ftable, df, row, c)
        c.execute(fsql)
        fresults = c.fetchall()
        fresult = fresults[0][0]
        if '=' in sql:
            sql += ' AND {fkey}={fresult}'.format(fkey=fkey, fresult=fresult)
        else:
            sql += ' {fkey}={fresult}'.format(fkey=fkey, fresult=fresult)

    return sql


def setup_function(function):
    add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL)
    add_user(fig.TEST_USER + '0', fig.TEST_PASS, fig.TEST_EMAIL)
    with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER) as db:
        access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA_FAIL,
                                                          'qiime',
                                                          reads=fig.TEST_READS,
                                                          barcodes=fig.TEST_BARCODES,
                                                          access_code=fig.TEST_CODE)


def test_tables():
    db = pms.connect('localhost', 'root', '', 'mmeds', local_infile=True)
    c = db.cursor()
    c.execute('SELECT user_id FROM user WHERE username="{}"'.format(fig.TEST_USER))
    user_id = int(c.fetchone()[0])

    df = pd.read_csv(fig.TEST_METADATA_FAIL, header=[0, 1], sep='\t')

    tables = df.columns.levels[0].tolist()
    tables.sort(key=lambda x: fig.TABLE_ORDER.index(x))
    del tables[tables.index('AdditionalMetaData')]
    for row in range(len(df)):
        for table in tables:
            # Create the query
            sql = build_sql(table, df, row, c)
            sql += ' AND user_id = ' + str(user_id)
            found = c.execute(sql)
            # Assert there exists at least one entry matching this description
            try:
                assert found > 0
            except AssertionError as e:
                print(c.fetchall())
                raise e


def test_junction_tables():
    db = pms.connect('localhost', 'root', '', 'mmeds', local_infile=True)
    c = db.cursor()
    df = pd.read_csv(fig.TEST_METADATA_FAIL, header=[0, 1], sep='\t')
    c.execute('SHOW TABLES')
    # Get the junction tables
    jtables = [x[0] for x in c.fetchall() if 'has' in x[0]]
    for row in range(len(df)):
        for jtable in jtables:
            sql = build_sql(jtable, df, row, c)
            jresult = c.execute(sql)
            # Ensure an entry exists for this value
            assert jresult > 0


def error_test_modify_tables():
    db = pms.connect('localhost', 'root', '', 'mmeds', local_infile=True)
    c = db.cursor()
    c.execute('SHOW TABLES')
    tables = [x[0] for x in c.fetchall() if 'protected' not in x[0]]
    del tables[tables.index('session')]
    del tables[tables.index('security_token')]
    del tables[tables.index('user')]
    for table in tables:
        sql = 'DESCRIBE {}'.format(table)
        c.execute(sql)
        result = c.fetchall()
        columns = [res[0] for res in result]

        sql = 'SELECT * FROM {}'.format(table)
        c.execute(sql)
        rows = c.fetchall()
        # Pick a row at random
        row = random.choice(rows)

        sql = 'DELETE FROM {} WHERE '.format(table)
        for i, column in enumerate(columns):
            value = row[i]
            if i == 0:
                sql += ' '
            else:
                sql += ' AND '
            # Add qoutes around string values
            if type(value) == str:
                sql += column + ' = "' + value + '"'
            # Otherwise check the absolute value of the difference is small
            # so that SQL won't fail to match floats
            else:
                sql += ' ABS(' + table + '.' + column + ' - ' + str(value) + ') <= 0.01'
        print(sql)
        c.execute(sql)


def error_test_table_protection():
    db = pms.connect('localhost', 'mmeds_user', 'password', 'mmeds', local_infile=True)
    c = db.cursor()
    c.execute('SHOW TABLES')
    protected_tables = [x[0] for x in c.fetchall() if 'protected' in x[0]]
    tables = [x.split('_')[-1] for x in protected_tables]
    for table, ptable in zip(tables, protected_tables):
        print(ptable)
        pass
