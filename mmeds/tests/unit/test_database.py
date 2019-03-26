from mmeds.database import Database
from mmeds.authentication import add_user, remove_user
from mmeds.error import TableAccessError
from mmeds.util import log
from prettytable import PrettyTable, ALL
from unittest import TestCase
import mmeds.config as fig
import pymysql as pms
import pandas as pd
import pytest

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


class DatabaseTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        """ Load data that is to be used by multiple test cases """
        add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL, testing=True)
        add_user(fig.TEST_USER_0, fig.TEST_PASS, fig.TEST_EMAIL, testing=True)
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA,
                                                              'qiime',
                                                              reads=fig.TEST_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE)

        with Database(fig.TEST_DIR_0, user='root', owner=fig.TEST_USER_0, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA_FAIL_0,
                                                              'qiime',
                                                              reads=fig.TEST_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE + '0')
        self.df0 = pd.read_csv(fig.TEST_METADATA_FAIL_0, header=[0, 1], skiprows=[2, 3, 4], sep='\t')
        self.df = pd.read_csv(fig.TEST_METADATA, header=[0, 1], skiprows=[2, 3, 4], sep='\t')
        # Connect to the database
        self.db = pms.connect('localhost',
                              'root',
                              '',
                              fig.SQL_DATABASE,
                              max_allowed_packet=2048000000,
                              local_infile=True)
        self.db.autocommit(True)
        self.c = self.db.cursor()

        # Get the user id
        self.c.execute('SELECT user_id FROM user WHERE username="{}"'.format(fig.TEST_USER))
        self.user_id = int(self.c.fetchone()[0])

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)
        remove_user(fig.TEST_USER_0, testing=True)
        self.db.close()

    def build_sql(self, table, row):
        """
        This function does the hard work of determining what a paticular table's
        entry should look like for a given row of the metadata file.
        ========================================================================
        :table: The name of the table for which to build the query
        :row: The row of the metadata file to check againt :table:
        ========================================================================
        The basic idea is that for each row of the input metadata file there exists
        a matching row in each table. The row in each table only contains part of
        the information from the row of the metadata, the part that relates to that
        table. However the table row is linked to rows in other tables that contain
        the rest of the information. This connection is stored as a foreign key in
        the table row.

        For example:
        A metadata row
        Table1	Table1	Table2	Table2
        ColA	ColB	ColC	ColD
        DataA	DataB	DataC	DataD

        Would be stored as follows:

        Table1
        ------------------------------
        Table1_key	ColA	ColB
        0		DataA	Datab

        Table2
        ------------------------------
        Table2_key	Table1_fkey	ColC	ColD
        2		0		DataC	DataD

        Checking Table1 is straight forward, just check that there is a row of Table1
        where ColA == DataA and ColB == DataB. The primary key (Table1_key) doesn't
        need to be checked against anything as it is simply a unique identifier within
        the table and doesn't exist in the original metadata file.

        Checking Table2 is more difficult as we need to verify that the table row
        matching ColC and ColD in the metadata is linked to a row in Table1 with the
        matching ColA and ColB. To do this we must find the primary key in Table1 where
        ColA == DataA and ColB == DataB. We can do this using the same method we used to
        originally check the row of Table1 except this time we record the primary key.

        This is essentially how build_sql works. For a given table it matches any regular
        columns using data from the metadata file (imported as a pandas dataframe).
        If it find any foreign key columns it recursively calls build_sql on the table
        that foreign key links to, returning what the value of that key should be.
        """
        sql = 'DESCRIBE {}'.format(table)
        self.c.execute(sql)
        result = self.c.fetchall()
        all_cols = [res[0] for res in result]
        foreign_keys = list(filter(lambda x: '_has_' not in x,
                                   list(filter(lambda x: '_id' in x,
                                               all_cols))))
        log('Got foreign keys')
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
            log('Column: {}'.format(column))
            value = self.df[table][column].iloc[row]
            if pd.isnull(value):
                value = 'NULL'
            # Only and AND if it's not the first argument
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
        if table in fig.PROTECTED_TABLES:
            sql += ' AND user_id = ' + str(self.user_id)

        log('COllect foreign keys')
        # Collect the matching foreign keys based on the infromation
        # in the current row of the data frame
        for fkey in foreign_keys:
            log('fkey: {}'.format(fkey))
            ftable = fkey.split('_id')[1]
            # Recursively build the sql call
            fsql = self.build_sql(ftable, row)
            self.c.execute(fsql)
            fresults = self.c.fetchall()
            # Get the resulting foreign key
            fresult = fresults[0][0]
            # Add it to the original query
            if '=' in sql:
                sql += ' AND {fkey}={fresult}'.format(fkey=fkey, fresult=fresult)
            else:
                sql += ' {fkey}={fresult}'.format(fkey=fkey, fresult=fresult)

        return sql

    ################
    #   Test SQL   #
    ################
    def test_a_tables(self):
        log('====== Test Database Start ======')
        log(self.df.columns)
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            self.df = db.import_ICD_codes(self.df)
        log(self.df.columns)
        tables = self.df.columns.levels[0].tolist()
        tables.sort(key=lambda x: fig.TABLE_ORDER.index(x))
        del tables[tables.index('AdditionalMetaData')]
        del tables[tables.index('ICDCode')]
        for row in range(len(self.df)):
            for table in tables:
                log('Query table {}'.format(table))
                # Create the query
                sql = self.build_sql(table, row)
                log(sql)
                found = self.c.execute(sql)
                if table == 'IllnessDetails':
                    log(sql)
                    log("{}:{}".format(table, row))
                    log(self.c.fetchall())
                # Assert there exists at least one entry matching this description
                try:
                    assert found > 0
                except AssertionError as e:
                    log(sql)
                    log("Didn't find entry {}:{}".format(table, row))
                    log(self.c.fetchall())
                    raise e

    def test_b_junction_tables(self):
        self.c.execute('SHOW TABLES')
        # Get the junction tables
        jtables = [x[0] for x in self.c.fetchall() if 'has' in x[0]]
        for row in range(len(self.df)):
            for jtable in jtables:
                log('Check table: {}'.format(jtable))
                sql = self.build_sql(jtable, row)
                jresult = self.c.execute(sql)
                # Ensure an entry exists for this value
                assert jresult > 0

    def test_c_table_protection(self):
        """
        The purpose of this test is to ensure that a user can only access data
        that they uploaded or that is made public. It does this by querying
        each of the protected tables as testuser0. For each row of results that
        is returned, it checks that a matching row exists in the metadata file
        uploaded by testuser0. There are other rows in these table as we know
        from previous test cases.
        """
        with Database(fig.TEST_DIR_0, user='mmedsusers', owner=fig.TEST_USER_0, testing=True) as db0:
            protected_tables = ['protected_' + x for x in fig.PROTECTED_TABLES]
            for table, ptable in zip(fig.PROTECTED_TABLES, protected_tables):
                # Confirm that trying to access the unprotected table
                # raises the appropriate error
                with pytest.raises(TableAccessError):
                    db0.execute('SELECT * FROM {}'.format(table))
                results, header = db0.execute('SELECT * FROM {}'.format(ptable))
                for result in results:
                    for i, col in enumerate(header):
                        if 'id' not in col:
                            # If the value is 'NULL' assert there is a NaN value in the dataframe
                            if result[i] == 'NULL':
                                assert self.df[table][col].isnull().values.any()
                            else:
                                if 'Date' in col:
                                    assert result[i] in pd.to_datetime(self.df0[table][col], yearfirst=True).tolist()
                                else:
                                    assert result[i] in self.df0[table][col].tolist()

    def test_d_metadata_checks(self):
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            warnings = db.check_repeated_subjects(self.df['Subjects'])
        assert warnings

        ndf = pd.read_csv(fig.UNIQUE_METADATA, header=[0, 1], skiprows=[2, 3, 4], sep='\t')
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            warnings = db.check_repeated_subjects(ndf['Subjects'])
            errors = db.check_user_study_name('Unique_Studay')
        assert not warnings
        assert not errors

    def test_e_clear_user_data(self):
        """
        Test that Database.clear_user_data('user') will
        empty all rows belonging exclusively to user
        and only those rows.
        """
        sql = 'SELECT user_id FROM {}.user WHERE username = "{}"'
        self.c.execute(sql.format(fig.SQL_DATABASE, fig.TEST_USER_0))
        user_id = int(self.c.fetchone()[0])
        log(user_id)
        table_counts = {}
        user_counts = {}

        # Check the tables that would be affected
        for table in fig.PROTECTED_TABLES + fig.JUNCTION_TABLES:
            # Get the total number of entries
            sql = 'SELECT COUNT(*) FROM {}'.format(table)
            self.c.execute(sql)
            table_counts[table] = int(self.c.fetchone()[0])
            # Get the number of entries belonging to the test user to be cleared
            sql = 'SELECT COUNT(*) FROM {} WHERE user_id = {}'.format(table, user_id)
            self.c.execute(sql)
            user_counts[table] = int(self.c.fetchone()[0])

        # Clear the tables
        with Database(fig.TEST_DIR_0, user='root', owner=fig.TEST_USER_0, testing=True) as db:
            db.clear_user_data(fig.TEST_USER_0)

        # Get the new table counts
        for table in fig.PROTECTED_TABLES + fig.JUNCTION_TABLES:
            # Get the new total number of entries
            sql = 'SELECT COUNT(*) FROM {}'.format(table)
            self.c.execute(sql)
            # Check that the difference is equal to the rows belonging to the cleared user
            assert int(self.c.fetchone()[0]) == table_counts[table] - user_counts[table]

    def test_e_import_ICD_codes(self):
        """ Test the parsing and loading of ICD codes. """
        for i, code in self.df['ICDCode']['ICDCode'].items():
            # Check the first character
            assert code.split('.')[0][0] == self.df['IllnessBroadCategory']['ICDFirstCharacter'].iloc[i]
            assert int(code.split('.')[0][1:]) == self.df['IllnessCategory']['ICDCategory'].iloc[i]
            assert code.split('.')[1][:-1] == self.df['IllnessDetails']['ICDDetails'].iloc[i]
            assert code.split('.')[1][-1] == self.df['IllnessDetails']['ICDExtension'].iloc[i]

    ####################
    #   Test MongoDB   #
    ####################
    def test_f_mongo_import(self):
        return
        """ Test the import of files into mongo. """
        # Get a random string to use for the code
        test_code = fig.get_salt(10)
        args = {}
        for i in range(5):
            args[fig.get_salt(5)] = fig.get_salt(10)
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            db.mongo_import('test_study', 'study_name', access_code=test_code, kwargs=args)
