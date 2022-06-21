import os
import warnings
import re

import mmeds.secrets as sec
import mmeds.config as fig
import mmeds.formatter as fmt
import mongoengine as men
import pymysql as pms
import pandas as pd

from datetime import datetime
from pathlib import Path
from prettytable import PrettyTable, ALL
from collections import defaultdict

from mmeds.error import (TableAccessError, MissingUploadError, MissingFileError, StudyNameError,
                         MetaDataError, NoResultError, InvalidSQLError)
from mmeds.util import (send_email, pyformat_translate, quote_sql, parse_ICD_codes)
from mmeds.database.metadata_uploader import MetaDataUploader
from mmeds.database.sql_builder import SQLBuilder
from mmeds.database.documents import MMEDSDoc
from mmeds.logging import Logger

DAYS = 13


# Used in test_cases
def upload_metadata(args):
    """
    This function wraps the metadatauploader class for when you want to run the upload
    in the current process rather than spinning up a new one
    """
    (subject_metadata, subject_type, specimen_metadata, owner, study_name, testing, access_code) = args

    p = MetaDataUploader(subject_metadata, subject_type, specimen_metadata, owner, 'qiime',
                         study_name, False, False, testing, access_code)
    return p.run()


def upload_otu(args):
    """
    Same idea as `upload_metadata` except uploads an otu table rather than fastq files. Upload_metadata should
    maybe re-named to clarify that it's actually a fastq upload.
    """
    (subject_metadata, subject_type, specimen_metadata, path, owner, study_name, otu_table, access_code) = args
    datafiles = {'otu_table': otu_table}
    p = MetaDataUploader(subject_metadata, subject_type, specimen_metadata, owner, 'sparcc', 'otu_table',
                         None, study_name, False, datafiles, False, True, access_code)
    p.run()
    return 0


def upload_lefse(args):
    """
    Same as the other two but this time for lefse tables.
    """
    (subject_metadata, subject_type, specimen_metadata, path, owner, study_name, lefse_table, access_code) = args
    datafiles = {'lefse_table': lefse_table}

    p = MetaDataUploader(subject_metadata, subject_type, specimen_metadata, owner, 'lefse', 'lefse_table',
                         None, study_name, False, datafiles, False, True, access_code)
    p.run()
    return 0


class Database:
    def __init__(self, path='.', user=sec.SQL_ADMIN_NAME, owner=None, testing=False):
        """
            Connect to the specified database.
            Initialize variables for this session.
            ---------------------------------------
            :path: A string. The path to the directory created for this session.
            :user: A string. What account to login to the SQL server with (user or admin).
            :owner: A string. The mmeds user account uploading or retrieving files.
            :testing: A boolean. Changes the connection parameters for testing.
        """
        warnings.simplefilter('ignore')

        self.path = Path(path) / 'database_files'
        self.IDs = defaultdict(dict)
        self.owner = owner
        self.user = user
        self.testing = testing

        # This is a great spot for a switch statement to
        # replaces these if/else blocks

        # If testing connect to test server
        if testing:
            # Connect as the specified user
            if user == sec.SQL_USER_NAME:
                self.db = pms.connect(host='localhost',
                                      user=sec.SQL_USER_NAME,
                                      password=sec.TEST_USER_PASS,
                                      database=fig.SQL_DATABASE,
                                      autocommit=True,
                                      local_infile=True)
            else:
                self.db = pms.connect(host='localhost',
                                      user='root',
                                      password=sec.TEST_ROOT_PASS,
                                      database=fig.SQL_DATABASE,
                                      autocommit=True,
                                      local_infile=True)
            # Connect to the mongo server
            self.mongo = men.connect(db='test',
                                     port=27017,
                                     host='127.0.0.1')
        # Otherwise connect to the deployment server
        else:
            if user == sec.SQL_USER_NAME:
                self.db = pms.connect(host=sec.SQL_HOST,
                                      user=user,
                                      password=sec.SQL_USER_PASS,
                                      database=sec.SQL_DATABASE,
                                      autocommit=True,
                                      local_infile=True)
            else:
                self.db = pms.connect(host=sec.SQL_HOST,
                                      user=user,
                                      password=sec.SQL_ADMIN_PASS,
                                      database=sec.SQL_DATABASE,
                                      autocommit=True,
                                      local_infile=True)
            self.mongo = men.connect(db=sec.MONGO_DATABASE,
                                     username=sec.MONGO_ADMIN_NAME,
                                     password=sec.MONGO_ADMIN_PASS,
                                     port=sec.MONGO_PORT,
                                     authentication_source=sec.MONGO_DATABASE,
                                     host=sec.MONGO_HOST)

        MMEDSDoc.objects.timeout(False)

        # Setup RLS for regular users
        if user == sec.SQL_USER_NAME:
            sql = 'SELECT set_connection_auth(%(owner)s, %(token)s)'
            with self.db.cursor() as cursor:
                cursor.execute(sql, {'owner': owner, 'token': sec.SECURITY_TOKEN})
            self.db.commit()

        # If the owner is None set user_id to 1
        if owner is None:
            self.user_id = 1
            self.email = fig.MMEDS_EMAIL
        # Otherwise get the user id for the owner from the database
        else:
            sql = 'SELECT `user_id`, `email` FROM `user` WHERE `user`.`username`=%(uname)s'
            with self.db.cursor() as cursor:
                cursor.execute(sql, {'uname': owner})
                result = cursor.fetchone()
            # Ensure the user exists
            if result is None:
                raise NoResultError('No account exists with the provided username and email.')
            self.user_id = int(result[0])
            self.email = result[1]

        self.check_file = fig.DATABASE_DIR / 'last_check.dat'

    def __del__(self):
        """ Clear the current user session and disconnect from the database. """
        if self.user == sec.SQL_USER_NAME:
            sql = 'SELECT unset_connection_auth(%(token)s)'
            with self.db.cursor() as cursor:
                cursor.execute(sql, {'token': sec.SECURITY_TOKEN})
            self.db.commit()
        if self.db:
            self.db.close()

    def __enter__(self):
        """ Allows database connection to be used via a 'with' statement. """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Delete the Database instance upon the end of the 'with' block. """
        del self

    ########################################
    #                MySQL                 #
    ########################################

    def get_table_contents(self, table):
        """ Return all the entries from the selected table """
        sql = 'SELECT * FROM `{table}`;'
        with self.db.cursor() as cursor:
            cursor.execute(quote_sql(sql, table=table))
            result = cursor.fetchall()
        table_text = '\n'.join(['\t'.join(['"{}"'.format(cell) for cell in row]) for row in result])
        return table_text

    def check_email(self, email):
        """ Check the provided email matches this user. """
        return email == self.email

    def get_email(self, username):
        """ Get the email that matches this user. """
        sql = 'SELECT `email` FROM `user` WHERE `username` = %(username)s'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'username': username})
            result = cursor.fetchone()
        if result is None:
            raise NoResultError('There is no entry for user {}'.format(username))
        return result[0]

    def get_privileges(self, username):
        """ Get the email that matches this user. """
        sql = 'SELECT `privilege` FROM `user` WHERE `username` = %(username)s'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'username': username})
            result = cursor.fetchone()
        if result is None:
            raise NoResultError('There is no entry for user {}'.format(username))
        return result[0]

    def get_hash_and_salt(self, username):
        """
        Get the hashed password and salt values for the specified user.
        """
        sql = 'SELECT `password`, `salt` FROM `user` WHERE `username` = %(username)s'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'username': username})
            result = cursor.fetchone()
        if result is None:
            raise NoResultError('There is no entry for user {}'.format(username))
        return result

    def get_all_usernames(self):
        """ Return all usernames currently in the database. """
        sql = 'SELECT `username` FROM `user`'
        with self.db.cursor() as cursor:
            cursor.execute(sql)
            result = cursor.fetchall()
        if result is None:
            raise NoResultError('There are no users in the database')
        return [name[0] for name in result]

    def set_mmeds_user(self, user):
        """
        Set the session to the current user of the webapp.
        This needs to be done before any user queries to ensure the
        row level security works as intended.
        """
        sql = 'SELECT set_connection_auth(%(user)s, %(token)s)'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'user': user, 'token': sec.SECURITY_TOKEN})
            set_user = cursor.fetchall()[0][0]
        self.db.commit()
        return set_user

    def format_html(self, text, header=None):
        """
        Applies PrettyTable HTML formatting to the provided string.
        ===========================================================
        :text: The text to format, should be the result of an SQL query
        :header: Optional, if querying a table will contain the column names
        """
        if header is not None:
            new_text = PrettyTable(header, border=True, hrules=ALL, vrules=ALL)
        else:
            new_text = PrettyTable(border=True, hrules=ALL, vrules=ALL)
        for line in text:
            new_text.add_row(list(map(str, line)))
        return new_text.get_html_string()

    def build_html_table(self, header, data):
        """
        Return an HTML formatted table containing the results of the provided query
        ===========================================================================
        :header: List, The column names
        :data: List of Tuples, The rows of the columns
        """

        # Add the table column labels
        html = '<table class="w3-table-all w3-hoverable">\n<thead>\n <tr class="w3-light-grey">\n'
        for column in header:
            html += '<th><b>{}</b></th>\n'.format(column)
        html += '</tr></thead>'

        Logger.error("Table contents")
        Logger.error(data)

        # Add each row
        for row in data:
            html += '<tr class="w3-hover-blue">'
            for i, value in enumerate(row):
                html += '<th> <a href="#{' + str(i) + '}' + '"> {} </a></th>'.format(value)
            html += '</tr>'

        html += '</table>'
        return html

    def format_results(self, header, data):
        """
        Takes the results from a query and formats them into a python dic
        ==================================================================
        :header: Header information for the query, typically column names for the queried table
        :data: The raw results from the query
        """
        formatted = defaultdict(list)
        for row in data:
            for column, value in zip(header, row):
                formatted[column].append(value)
        return formatted

    def get_table_headers(self, sql, filter_ids):
        """
        Get the headers for the columns requested in the provided query
        =====================================
        :sql: A String, The query in question
        :filter_ids: A Boolean, If true filter out foreign keys from the result
        """
        match_sql = sql.split('FROM')[1]
        try:
            # Get headers from a joined table
            if 'JOIN' in sql:
                table = sql[sql.find('('):sql.rfind(')')+1]
            else:  # Otherwise get headers from a single table
                # \S is a pattern that matches any non-whitespace character
                # * matches any number of repititions of the preciding match pattern
                table = re.search(r'`\S*`', match_sql)[0].strip('`')
            Logger.error(f'Getting headers for table {table}')
            with self.db.cursor() as cursor:
                cursor.execute(quote_sql('DESCRIBE {table}', table=table))
                result = cursor.fetchall()
        except pms.err.ProgrammingError as e:
            Logger.error(str(e))
            raise InvalidSQLError(e.args[1] + f'\nOriginal Query\nDESCRIBE {table}')
        Logger.error(f'result {result}')
        header = [x[0] for x in result]
        Logger.error(f'header {header}')
        if filter_ids:
            # Remove foreign keys
            header = [col for col in header if 'id' not in col]
        return header

    def execute(self, sql, filter_ids=True):
        """
        Execute the provided sql code
        ====================================
        :sql: A string, Contains a SQL query
        :filter_ids: A Boolean, when true remove all primary and foreign keys from the results
        """
        header = None
        # If the user is not an admin automatically map tables in the query
        # to their protected views
        if self.user not in {sec.SQL_ADMIN_NAME, 'root'}:
            # Replace references to protected tables to their view counterparts
            for table in fig.PROTECTED_TABLES:
                if table in sql:
                    sql = sql.replace(' ' + table, ' protected_' + table)
                    sql = sql.replace(' `' + table, ' `protected_' + table)
                    sql = sql.replace('=`' + table, '=`protected_' + table)
                    sql = sql.replace('=' + table, '=protected_' + table)
        try:
            # Get the table column headers
            # To work properly this requires the table names to be in back ticks e.g. `TableName`
            if 'from' in sql.casefold():
                header = self.get_table_headers(sql, filter_ids)
                # Expand * to limit results
                sql = sql.replace('*', ', '.join(header))

            with self.db.cursor() as cursor:
                cursor.execute(sql)
                data = cursor.fetchall()
            self.db.commit()
        except pms.err.OperationalError as e:
            Logger.error('OperationalError')
            Logger.error(str(e))
            # If it's a select command denied error
            if e.args[0] == 1142:
                raise TableAccessError(e.args[1] + f'\nOriginal Query\n{sql}')
            raise e
        except (pms.err.ProgrammingError, pms.err.InternalError) as e:
            Logger.error(str(e))
            data = str(e)
            raise InvalidSQLError(e.args[1] + f'\nOriginal Query\n{sql}')
        return data, header

    def delete_sql_rows(self):
        """
        Deletes every row from every table in the currently connected database.
        """
        with self.db.cursor() as cursor:
            cursor.execute('SHOW TABLES')
            tables = [x[0] for x in cursor.fetchall()]
        # Skip the user table
        tables.remove('user')
        r_tables = []
        while True:
            for table in tables:
                if 'View' not in table:
                    try:
                        with self.db.cursor() as cursor:
                            cursor.execute(quote_sql('DELETE FROM {table}', table=table))
                        self.db.commit()
                    except pms.err.IntegrityError:
                        r_tables.append(table)
            if not r_tables:
                break
            else:
                tables = r_tables
                r_tables = []

    def get_col_values_from_table(self, column, table):
        """
        Returns the values of the specified column of the specified table
        """
        sql = quote_sql('SELECT {column} FROM {table}', column=column, table=table)
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'column': column, 'table': table})
            data = cursor.fetchall()
        return data

    def add_user(self, username, password, salt, email, privilege_level, reset_needed=0):
        """
        Add a new user to the MySQL with the specified parameters.
        ==========================================================
        :username: A String. The new users name
        :password: A string. A hash of the users provided password + salt
        :salt: A string. A short unique string used to ensure that if the same password
            is used by multiple users they won't have the same hashes
        :email: A string. The email of the user.
        :privilege_level: An int. For now either 0 or 1. 0 by default, but lab users
            can be promoted to privilege_level 1 for advanced features and access to
            all uploaded studies
        :reset_needed: An int. An indicator, when 1 the user needs to update their password
        """
        with self.db.cursor() as cursor:
            cursor.execute('SELECT MAX(user_id) FROM user')
            user_id = int(cursor.fetchone()[0]) + 1
        # Create the SQL to add the user
        sql = 'INSERT INTO `user` (user_id, username, password, salt, email, privilege, reset_needed)'
        sql += ' VALUES (%(id)s, %(uname)s, %(pass)s, %(salt)s, %(email)s, %(privilege)s, %(reset_needed)s);'

        with self.db.cursor() as cursor:
            cursor.execute(sql, {'id': user_id,
                                 'uname': username,
                                 'pass': password,
                                 'salt': salt,
                                 'email': email,
                                 'privilege': privilege_level,
                                 'reset_needed': reset_needed
                                 })
        self.db.commit()
        Logger.info('USER {} HAS BEEN ADDED'.format(username))

    def set_reset_needed(self, reset_needed):
        """
        Update the 'reset_needed' value in the `user` table of the MySQL DB.
        This forces the user to change their password before continuing.
        """
        reset_needed = int(reset_needed)
        sql = 'SELECT * FROM `user` WHERE `username` = %(uname)s'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'uname': self.owner})
            result = cursor.fetchone()
            # Delete the old entry for the user
            sql = 'DELETE FROM `user` WHERE `user_id` = %(id)s'
            cursor.execute(sql, {'id': result[0]})

            # Insert the user with the updated value
            sql = 'INSERT INTO `user` (user_id, username, password, salt, email, privilege, reset_needed) VALUES\
                (%(id)s, %(uname)s, %(pass)s, %(salt)s, %(email)s, %(privilege)s, %(reset_needed)s);'
            cursor.execute(sql, {
                'id': result[0],
                'uname': result[1],
                'pass': result[2],
                'salt': result[3],
                'email': result[4],
                'privilege': result[5],
                'reset_needed': reset_needed
            })
        self.db.commit()

    def get_reset_needed(self):
        """ Return the 'reset_needed' value from the `mmeds_data1`.`user` table """
        sql = 'SELECT * FROM `user` WHERE `username` = %(uname)s'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'uname': self.owner})
            result = cursor.fetchone()
            return result[6]

    def remove_user(self, username):
        """ Remove a user from the database. """
        sql = 'DELETE FROM `user` WHERE `username`=%(uname)s'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'uname': username})
        self.db.commit()

    def clear_user_data(self, username):
        """
        Remove all data in the database belonging to username.
        ======================================================
        :username: The name of the user to remove files for
        """
        # Get the user_id for the provided username
        sql = 'SELECT `user_id` FROM `user` where `username`=%(uname)s'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'uname': username})
            user_id = int(cursor.fetchone()[0])

        # Only delete values from the tables that are protected
        tables = list(filter(lambda x: x in fig.PROTECTED_TABLES,
                             fig.TABLE_ORDER)) + fig.JUNCTION_TABLES
        # Start with the tables that link to other tables rather than one that are linked to
        tables.reverse()
        for table in tables:
            try:
                # Remove all values from the table belonging to that user
                sql = quote_sql('DELETE FROM {table} WHERE user_id=%(id)s', table=table)
                with self.db.cursor() as cursor:
                    cursor.execute(sql, {'id': user_id})
            except pms.err.IntegrityError as e:
                # If there is a dependency remaining
                Logger.info(e)
                Logger.info('Failed on table {}'.format(table))
                raise MetaDataError(e.args[0])

        # Commit the changes
        self.db.commit()

        # Clear the mongo files
        self.clear_mongo_data(username)

    def add_metadata(self, entry_frame, main_table, known_id):
        """
        Handles the import of metadata from a file containing
        only some columns related to an existing dataset.
        =====================================================
        :entry_frame: A pandas dataframe containing one row of the
                        data from the metadata file being uploaded
        :main_table: The primary table that this upload links to. So
                        for a new Aliquot the :main_table: is Specimen,
                        a new Sample, the :main_table: is Aliquot
        :known_id: The id of the primary key in the main table that
                        this row relates to
        """

        # Maps foreign keys to the tables that require them
        # TODO this should probably be built out in config.py
        required_fkeys = defaultdict(set)

        # Add foreign key columns where necessary
        tables = list(set([index[0] for index in entry_frame.columns]))
        for table in tables:
            fkey_cols = [col for col in fig.ALL_TABLE_COLS[table] if '_id' in col]
            for col in fkey_cols:
                required_fkeys[col].add(table)
                if col == f'{main_table}_id{main_table}':
                    entry_frame[(table, f'{main_table}_id{main_table}')] = known_id

        # Sort the tables into the correct order to fill them
        tables.sort(key=fig.TABLE_ORDER.index)
        for i, table in enumerate(tables):
            Logger.info('Query table {}'.format(table))
            row_data = {key: value[0] for key, value in entry_frame[table].to_dict().items()}

            # Create a new known keys dict
            known_fkeys = {f'{main_table}_id{main_table}': known_id}
            fkey = self.insert_into_table(row_data, table, entry_frame, known_fkeys)
            # Only add the keys if included in the table
            for key_table in tables:
                if key_table in required_fkeys[f'{table}_id{table}']:
                    entry_frame[(key_table, f'{table}_id{table}')] = fkey
            known_fkeys[f'{table}_id{table}'] = fkey

    def generate_aliquot_id(self, generate_id, StudyName, SpecimenID, **kwargs):
        """
        Generate a new id for the aliquot with the given weight
        =======================================================
        :generate_id: A Boolean, when true a new ID will be created from the existing SpecimenID
                If false the Aliquots ID must already be in kwargs
        :StudyName: Name of study this aliquot will belong to
        :SpecimenID: A string. The ID of the Specimen this Aliquot is taken from
        :kwargs: A dictionary. The other properties of this Aliquot, other than the ID
        """

        # Get the SQL id of the Specimen this should be associated with
        data, header = self.execute(fmt.SELECT_COLUMN_SPECIMEN_QUERY.format(column='`idSpecimen`',
                                                                            StudyName=StudyName,
                                                                            SpecimenID=SpecimenID), False)
        # This refers to the primary key of the Specimen this Aliquot is taken from
        idSpecimen = int(data[0][0])

        # Get the number of Aliquots previously created from this Specimen
        with self.db.cursor() as cursor:
            cursor.execute('SELECT COUNT(AliquotID) FROM `Aliquot` WHERE `Specimen_idSpecimen` = %(idSpecimen)s',
                           {'idSpecimen': idSpecimen})

            aliquot_count = cursor.fetchone()[0]

        # Create the human readable ID
        if generate_id:
            AliquotID = '{}-Aliquot{}'.format(SpecimenID, aliquot_count)
            kwargs['AliquotID'] = AliquotID
        multi_index = pd.MultiIndex.from_tuples([fig.MMEDS_MAP[key] for key in kwargs.keys()])
        entry_frame = pd.DataFrame([kwargs.values()], columns=multi_index)

        # Create a dict for storing the already known fkeys
        entry_frame[('Aliquot', 'Specimen_idSpecimen')] = idSpecimen

        self.add_metadata(entry_frame, 'Specimen', idSpecimen)

        # TODO get rid of this if I drop support for individual id creation
        if generate_id:
            return AliquotID

    def generate_sample_id(self, generate_id, StudyName, AliquotID, **kwargs):
        """
        Generate a new id for the sample with the given weight
        =======================================================
        :generate_id: A Boolean, when true a new ID will be created from the existing AliquotID
                If false the Samples ID must already be in kwargs
        :StudyName: Name of study this Sample belongs to
        :AliquotID: A string. The ID of the Aliquot this Sample is taken from
        :kwargs: A dictionary. The other properties of this Sample, other than the ID
        """

        # Get the SQL id of the Aliquot this should be associated with
        data, header = self.execute(fmt.GET_ALIQUOT_QUERY.format(column='idAliquot',
                                                                 AliquotID=AliquotID), False)
        idAliquot = int(data[0][0])
        # Get the number of Samples previously created from this Aliquot
        with self.db.cursor() as cursor:
            cursor.execute('SELECT COUNT(SampleID) FROM Sample WHERE Aliquot_idAliquot = %(idAliquot)s',
                           {'idAliquot': idAliquot})

            aliquot_count = cursor.fetchone()[0]

        # Create the human readable ID
        if generate_id:
            SampleID = '{}-Sample{}'.format(AliquotID, aliquot_count)
            kwargs['SampleID'] = SampleID
        multi_index = pd.MultiIndex.from_tuples([fig.MMEDS_MAP[key] for key in kwargs.keys()])
        entry_frame = pd.DataFrame([kwargs.values()], columns=multi_index)

        # Create a dict for storing the already known fkeys
        entry_frame[('Sample', 'Aliquot_idAliquot')] = idAliquot

        self.add_metadata(entry_frame, 'Aliquot', idAliquot)

        if generate_id:
            return SampleID

    def add_subject_data(self, generate_id, StudyName, HostSubjectId, **kwargs):
        """
        Like `generate_aliquot_id` and `generate_sample_id` but for new subjects.
        It doesn't have functionality for generating the ID within this method so that parameter
        is just there for consistency. Really it should probably be a default parameter
        of `generate_id=False` for all these methods.
        """
        # Get the SQL id of the subject this should be associated with
        data, header = self.execute(fmt.SELECT_COLUMN_SUBJECT_QUERY.format(column='idSubjects',
                                                                           HostSubjectId=HostSubjectId,
                                                                           StudyName=StudyName), False)
        idSubjects = int(data[0][0])

        # Create a multi-index to stand in for the subject metadata
        multi_index = pd.MultiIndex.from_tuples([fig.MMEDS_MAP[key] for key in kwargs.keys()])
        entry_frame = parse_ICD_codes(pd.DataFrame([kwargs.values()], columns=multi_index))
        entry_frame.drop(('ICDCode', 'ICDCode'), axis=1, inplace=True)
        self.add_metadata(entry_frame, 'Subjects', idSubjects)

    def insert_into_table(self, data, table, entry_frame, known_fkeys):
        """
        Insert the provided data into the specified table. This has to build out a full
        row for the table, foreign keys and all.
        --------------------------------------------------
        :data: A dict containing the data for this row
        :table: A string. The name of the table to add data to.
        :entry_frame: A dataframe containing the data to enter as a new row
        :known_fkeys: The already known foreign keys for this table
        """
        # Create the query
        builder = SQLBuilder(entry_frame, self.db, self.owner)
        sql, args = builder.build_sql(table, 0, known_fkeys)
        with self.db.cursor() as cursor:
            cursor.execute(sql, args)
            Logger.sql_debug(sql, args)
            fkey = cursor.fetchone()
        Logger.debug(f"Found foreign key is {fkey}")

        # If there is no matching row
        if fkey:
            fkey = fkey[0]
        else:
            # Create a new key for that table
            sql = quote_sql('SELECT MAX({idtable}) FROM {table}', idtable=f'id{table}', table=table)
            with self.db.cursor() as cursor:
                cursor.execute(sql)
                fkey = cursor.fetchone()[0] + 1

            # Add the new id
            data[f'id{table}'] = fkey

            # Get the user id if necessary
            if table in fig.PROTECTED_TABLES:
                data['user_id'] = self.user_id

            # Replace nans with none
            for key in data.keys():
                if pd.isna(data[key]):
                    data[key] = None

            # Build the insertion query
            sql = fmt.INSERT_QUERY.format(columns=', '.join([f'`{col}`' for col in data.keys()]),
                                          values=', '.join([f'%({col})s' for col in data.keys()]),
                                          table=table)
            Logger.sql_debug(sql, data)
            # Insert the new row into the table
            with self.db.cursor() as cursor:
                cursor.execute(sql, data)
            self.db.commit()

        # Return the key
        return fkey

    def create_ids_file(self, study_name, id_type):
        """
        Create a file containing the requested ID information and return the path to it.
        ================================================================================
        :study_name: A string. The name of the study to get IDs from.
        :id_type: A string. The type of IDs to return. Sample, Aliquot, etc
        """
        id_list = []
        with self.db.cursor() as cursor:
            # Get all the specimen in the given study
            cursor.execute(fmt.SELECT_SPECIMEN_QUERY.format(StudyName=study_name))
            specimen = cursor.fetchall()
            for speciman in specimen:
                # Get each Specimen ID
                cursor.execute(fmt.SELECT_COLUMN_SPECIMEN_QUERY.format(column='idSpecimen',
                                                                       StudyName=study_name,
                                                                       SpecimenID=speciman[0]))
                id_specimen = cursor.fetchone()

                aliquot_data, header = self.execute(fmt.SELECT_ALIQUOT_QUERY.format(idSpecimen=id_specimen[0]))

                # If aliquots were requested this create the table for them
                if id_type == 'aliquot':
                    id_list += ['\t'.join([str(col) for col in row]) for row in aliquot_data]
                elif id_type == 'sample':  # Otherwise...
                    for ali_id, _ in aliquot_data:
                        cursor.execute(fmt.GET_ALIQUOT_QUERY.format(column='idAliquot', AliquotID=ali_id))
                        id_ali = cursor.fetchone()[0]
                        sample_data, header = self.execute(fmt.SELECT_SAMPLE_QUERY.format(idAliquot=id_ali))
                        id_list += ['\t'.join([str(col) for col in row]) for row in sample_data]

        # Make sure the output location for this is valid
        if not self.path.is_dir():
            self.path.mkdir()
        id_table = self.path / f'{study_name}_{id_type}_id_table.tsv'
        id_table.write_text('\n'.join(['\t'.join(header)] + id_list))
        return id_table

    ########################################
    #               MongoDB                #
    ########################################
    def create_access_code(self, check_code=None, length=20):
        """ Creates a unique code for identifying a mongo db document """
        if check_code is None:
            check_code = fig.get_salt(20)
        code = check_code
        count = 0
        # Ensure no document exists with the given access code
        while MMEDSDoc.objects(access_code=code).first():
            code = check_code + '-' + str(count)
            count += 1
        return code

    def mongo_clean(self, access_code):
        """ Delete all mongo objects with the given access_code """
        obs = MMEDSDoc.objects(access_code=access_code)
        for ob in obs:
            ob.delete()

    def modify_data(self, new_data, access_code, data_type):
        """
        :new_data: A string or pathlike pointing to the location of the new data file.
        :access_code: The code for identifying this dataset.
        :data_type: A string. Either 'reads' or 'barcodes' depending on which is being modified.
        """
        mdata = MMEDSDoc.objects(access_code=access_code, owner=self.owner).first()
        mdata.last_accessed = datetime.utcnow()

        # Remove the old data file if it exits
        if mdata.files.get(data_type) is not None:
            Path(mdata.files[data_type]).unlink()

        mdata.files[data_type] = str(new_data)
        mdata.save()

    def reset_access_code(self, study_name, email):
        """
        Reset the access_code for the study with the matching name and email.
        """
        # Get a new code
        new_code = fig.get_salt(50)
        # Get the mongo document
        mdata = MMEDSDoc.objects(study_name=study_name, owner=self.owner, email=email).first()
        mdata.last_accessed = datetime.utcnow()
        mdata.access_code = new_code
        mdata.save()
        send_email(email, self.owner, new_code)

    def change_password(self, new_password, new_salt):
        """ Change the password for the current user. """

        # Verify the username is okay
        if self.owner == 'Public' or self.owner == 'public':
            raise NoResultError('No account exists with the providied username and email.')
        # Get the user's information from the user table
        sql = 'SELECT * FROM `user` WHERE `username` = %(uname)s'
        with self.db.cursor() as cursor:
            cursor.execute(sql, {'uname': self.owner})
            result = cursor.fetchone()

            # Delete the old entry for the user
            sql = 'DELETE FROM `user` WHERE `user_id` = %(id)s'
            cursor.execute(sql, {'id': result[0]})

            # Insert the user with the updated password
            sql = 'INSERT INTO user (user_id, username, password, salt, email, privilege, reset_needed) VALUES\
                (%(id)s, %(uname)s, %(pass)s, %(salt)s, %(email)s, %(priv)s, %(reset_needed)s);'
            cursor.execute(sql, {
                'id': result[0],
                'uname': result[1],
                'pass': new_password,
                'salt': new_salt,
                'email': result[4],
                'priv': result[5],
                'reset_needed': 0
            })
        self.db.commit()
        return True

    def update_metadata(self, access_code, filekey, value):
        """
        Add a file to a metadata object
        ====================================
        :access_code: Code identifiying the document to update
        :filekey: The key the new file should be indexed under
        :value: Either a path to a file or a dictionary containing
                file locations in a subdirectory
        """
        Logger.info('Update metadata with {}: {}'.format(filekey, value))
        mdata = MMEDSDoc.objects(access_code=access_code, owner=self.owner).first()
        mdata.last_accessed = datetime.utcnow()
        mdata.files[filekey] = value
        mdata.save()

    def check_repeated_subjects(self, df, subject_type, subject_col=-2):
        """
        Checks for users that match those already in the database.
        """
        warnings = []
        # If there is no subjects table in the metadata this
        # dataframe will be empty. If there are no subjects there
        # can't be any repeated subjects so it will just return the
        # empty list
        if not df.empty:
            if subject_type == 'human':
                initial_sql = """SELECT * FROM `Subjects` WHERE"""
            elif subject_type == 'animal':
                initial_sql = """SELECT * FROM `AnimalSubjects` WHERE"""
            # Go through each row
            for j in range(len(df.index)):
                sql = initial_sql
                args = {}
                # Check if there is an entry already in the database that matches every column
                for i, column in enumerate(df):
                    value = df[column][j]
                    if pd.isnull(value):  # Use NULL for NA values
                        value = '\\N'
                    if i == 0:
                        sql += ' '
                    else:
                        sql += ' AND '
                    # Add quotes around string values
                    sql += quote_sql(('{column} = %({column})s'), column=column)
                    result = pyformat_translate(value)
                    args['`{}`'.format(column)] = result
                sql += ' AND user_id = %(id)s'
                args['id'] = self.user_id
                try:
                    with self.db.cursor() as cursor:
                        found = cursor.execute(sql, args)
                except pms.err.InternalError as e:
                    raise MetaDataError(e.args[1])
                if found >= 1:
                    Logger.info(sql)
                    Logger.info(args)
                    warning = '{row}\t{col}\tSubject in row {row} already exists in the database.'
                    warnings.append(warning.format(row=j, col=subject_col))
        return warnings

    def check_user_study_name(self, study_name):
        """ Checks if the current user has already uploaded a study with the same name. """

        sql = 'SELECT * FROM `Study` WHERE `user_id` = %(id)s and `Study`.`StudyName` = %(study)s'
        with self.db.cursor() as cursor:
            found = cursor.execute(sql, {'id': self.user_id, 'study': study_name})

        # Ensure multiple studies aren't uploaded with the same name
        if found >= 1 and not self.testing:
            result = ['-1\t-1\tUser {} has already uploaded a study with name {}'.format(self.owner, study_name)]
        else:
            result = []
        return result

    def get_mongo_files(self, access_code, check_owner=True):
        """ Return mdata.files, mdata.path for the provided access_code. """
        if check_owner:
            mdata = MMEDSDoc.objects(access_code=access_code, owner=self.owner).first()
        else:
            mdata = MMEDSDoc.objects(access_code=access_code).first()

        # Raise an error if the upload does not exist
        if mdata is None:
            raise MissingUploadError()
        for path in mdata.files.values():
            if not Path(path).exists():
                raise MissingFileError('File {}, does not exist'.format(path))

        mdata.last_accessed = datetime.utcnow()
        mdata.save()
        return mdata.files, mdata.path

    def get_metadata(self, access_code):
        """
        Return the MMEDSDoc object.
        This object should be treated as read only.
        Any modifications should be done through the Database class.
        """
        return MMEDSDoc.objects(access_code=access_code, owner=self.owner).first()

    def get_doc(self, access_code, check_owner=True):
        """
        Return the MMEDSDoc object.
        This object should be treated as read only.
        Any modifications should be done through the Database class.
        """
        if check_owner:
            doc = MMEDSDoc.objects(access_code=access_code, owner=self.owner).first()
        else:
            doc = MMEDSDoc.objects(access_code=access_code).first()

        if doc is None:
            raise MissingUploadError('Upload does not exist for user {} with code {}'.format(self.owner, access_code))
        return doc

    def check_upload(self, access_code, check_owner=True):
        if check_owner:
            obs = MMEDSDoc.objects(access_code=access_code, owner=self.owner)
        else:
            obs = MMEDSDoc.objects(access_code=access_code)
        if not obs:
            raise MissingUploadError()

    def check_study_name(self, study_name):
        """ Verifies the provided study name is valid and not already in use. """
        if not study_name.replace('_', '').isalnum():
            raise StudyNameError("Only alpha numeric characters and '_' are allowed in the study name")
        if MMEDSDoc.objects(study_name=study_name, doc_type='study'):
            raise StudyNameError(f"Study name {study_name} already in use")

    def check_sequencing_run_name(self, run_name):
        """ Verifies the provided sequencing run name is valid and not already in use. """
        if not run_name.replace('_', '').isalnum():
            raise StudyNameError("Only alpha-numeric characters and '_' are allowed in the sequencing run name")
        if MMEDSDoc.objects(study_name=run_name, doc_type='sequencing_run'):
            raise StudyNameError(f"Sequencing Run name {run_name} already in use")

    def get_sequencing_run_locations(self, metadata, user, column=("RawDataProtocol", "RawDataProtocolID")):
        """ Returns the list of sequencing runs as a dict of dir paths """
        df = pd.read_csv(metadata, sep='\t', header=[0, 1], skiprows=[2, 3, 4])

        # Store run names from metadata
        runs = []
        for run in df[column]:
            if run not in runs:
                runs.append(run)

        # Get paths, these should exist due to already checking during validation
        run_paths = {}
        for run in runs:
            doc = MMEDSDoc.objects(doc_type='sequencing_run', study_name=run, owner=user).first()
            run_paths[run] = {}
            # Get individual files within sequencing run directories
            with open(Path(doc.path) / fig.SEQUENCING_DIRECTORY_FILE, "rt") as f:
                content = f.read().split('\n')
                for line in content:
                    if ": " in line:
                        key, val = line.split(": ")
                        run_paths[run][key] = Path(doc.path) / val

        return run_paths

    def get_sequencing_run_from_name(self, run_name):
        doc = MMEDSDoc.objects(doc_type='sequencing_run', study_name=run_name).first()
        run_paths = {'name': run_name}

        # Get individual files within sequencing run directory
        with open(Path(doc.path) / fig.SEQUENCING_DIRECTORY_FILE, "rt") as f:
            content = f.read().split('\n')
            for line in content:
                if ": " in line:
                    key, val = line.split(": ")
                    run_paths[key] = Path(doc.path) / val

        return run_paths

    def get_all_studies(self):
        """ Return all studies currently stored in the database. """
        return MMEDSDoc.objects(doc_type='study')

    def get_all_analyses(self):
        """ Return all analyses currently stored in the database. """
        return MMEDSDoc.objects(doc_type='analysis')

    def get_all_sequencing_runs(self):
        """ Return all sequencing runs currently stored in the database. """
        return MMEDSDoc.objects(doc_type='sequencing_run')

    def get_all_user_sequencing_runs(self, user):
        """ Return all sequencing runs currently stored in the database owned by USER. """
        return MMEDSDoc.objects(doc_type='sequencing_run', owner=user)

    def get_all_user_studies(self, user):
        """ Return all studies currently stored in the database owned by USER. """
        return MMEDSDoc.objects(doc_type='study', owner=user)

    def get_all_analyses_from_study(self, access_code):
        """ Return all studies currently stored in the database. """
        return MMEDSDoc.objects(study_code=access_code)

    def check_files(self, access_code):
        """ Check that all files associated with the study actually exist. """
        mdata = MMEDSDoc.objects(access_code=access_code, owner=self.owner).first()
        empty_files = []
        for key in mdata.files.keys():
            if not os.path.exists(mdata.files[key]):
                empty_files.append(mdata.files[key])
                del mdata.files[key]
        return empty_files

    def delete_mongo_documents(self):
        """ Clear all metadata documents. This may be necessary if the MMEDSDoc class is modified """
        data = list(MMEDSDoc.objects())
        for doc in data:
            doc.delete()

    def clear_mongo_data(self, username):
        """ Clear all metadata documents associated with the provided username. """
        data = list(MMEDSDoc.objects(owner=username))
        for doc in data:
            doc.delete()

    def get_study_from_access_code(self, code):
        """ Get the document for the study with the given access_code"""
        return MMEDSDoc.objects(access_code=code).first()

    def get_access_code_from_study_name(self, study, username):
        """ Returns the access code of the study with the provided properties """
        return MMEDSDoc.objects(owner=username, study_name=study).first().access_code

    def get_docs(self, **kwargs):
        """
        This is a general purpose getter. It passes all arugments provided into
        the mongoengine objects request. Mostly I've used this when debugging document
        issues through mongoengine and the python shell.
        """
        return MMEDSDoc.objects(**kwargs)
