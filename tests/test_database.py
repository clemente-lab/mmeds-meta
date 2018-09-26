from mmeds.database import Database
from mmeds.authentication import add_user
from prettytable import PrettyTable, ALL
import mmeds.config as fig
import pymysql as pms
import pandas as pd

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


def setup_function(function):
    add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL)
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
            sql = 'DESCRIBE {}'.format(table)
            c.execute(sql)
            result = c.fetchall()
            columns = list(filter(lambda x: 'id' not in x, [res[0] for res in result]))
            table_df = df[table]
            sql = 'SELECT * FROM {} WHERE '.format(table)
            # Create an sql query to match the data from this row of the input file
            for i, column in enumerate(columns):
                value = table_df[column].iloc[row]
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
                if table == 'Subjects':
                    sql += ' AND user_id = ' + str(user_id)
            found = c.execute(sql)
            # Assert there exists at least one entry matching this description
            assert found > 0
