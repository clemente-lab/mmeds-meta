from mmeds.database import Database
from mmeds.authentication import add_user, remove_user
from mmeds.error import TableAccessError
from mmeds.util import log, parse_ICD_codes
from prettytable import PrettyTable, ALL
from unittest import TestCase
import mmeds.config as fig
import mmeds.secrets as sec
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
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=True)
        add_user(fig.TEST_USER_0, sec.TEST_PASS, fig.TEST_EMAIL, testing=True)
        log('about to read in')
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA,
                                                              'qiime',
                                                              reads=fig.TEST_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE)

        with Database(fig.TEST_DIR_0, user='root', owner=fig.TEST_USER_0, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA_0,
                                                              'qiime',
                                                              reads=fig.TEST_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE + '0')
        self.df0 = parse_ICD_codes(pd.read_csv(fig.TEST_METADATA_0, header=[0, 1], skiprows=[2, 3, 4], sep='\t'))
        self.df = parse_ICD_codes(pd.read_csv(fig.TEST_METADATA, header=[0, 1], skiprows=[2, 3, 4], sep='\t'))
        # Connect to the database
        self.db = pms.connect('localhost',
                              'root',
                              '',
                              fig.SQL_DATABASE,
                              max_allowed_packet=2048000000,
                              local_infile=True)
        self.db.autocommit(True)
        self.c = self.db.cursor()
        log('after read in')
        self.c.execute('SELECT * FROM Subjects')
        log(self.c.fetchall())
        self.mmeds_db = Database(user='root', owner=fig.TEST_USER, testing=True)
        log('after connect')
        self.c.execute('SELECT * FROM Subjects')
        log(self.c.fetchall())

        # Get the user id
        self.c.execute('SELECT user_id FROM user WHERE username="{}"'.format(fig.TEST_USER))
        self.user_id = int(self.c.fetchone()[0])

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)
        remove_user(fig.TEST_USER_0, testing=True)
        self.db.close()
        del self.mmeds_db

    ################
    #   Test SQL   #
    ################
    def test_a_tables(self):
        log('====== Test Database Start ======')
        tables = self.df.columns.levels[0].tolist()
        tables.sort(key=lambda x: fig.TABLE_ORDER.index(x))
        del tables[tables.index('AdditionalMetaData')]
        del tables[tables.index('ICDCode')]
        for row in range(len(self.df)):
            for table in tables:
                log('Query table {}'.format(table))
                # Create the query
                sql, args = self.mmeds_db.build_sql(self.df, table, row)
                log(sql)
                log(args)
                found = self.c.execute(sql, args)
                log(found)
                if table == 'IllnessDetails':
                    log(sql)
                    log("{}:{}".format(table, row))
                    log(self.c.fetchall())
                # Assert there exists at least one entry matching this description
                try:
                    assert found > 0
                except AssertionError as e:
                    log(self.df.iloc[row])
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
                sql, args = self.mmeds_db.build_sql(self.df, jtable, row)
                jresult = self.c.execute(sql, args)
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
