import os
import shutil
import warnings

import mmeds.secrets as sec
import mmeds.config as fig
import mongoengine as men
import pymysql as pms
import cherrypy as cp
import pandas as pd

from datetime import datetime
from pathlib import WindowsPath, Path
from prettytable import PrettyTable, ALL
from collections import defaultdict
from mmeds.config import TABLE_ORDER, MMEDS_EMAIL, USER_FILES, SQL_DATABASE, get_salt
from mmeds.error import TableAccessError, MissingUploadError, MetaDataError, NoResultError, InvalidSQLError
from mmeds.util import send_email, pyformat_translate, quote_sql, parse_ICD_codes, sql_log, log
from mmeds.documents import StudyDoc, AnalysisDoc

DAYS = 13


# Used in test_cases
def upload_metadata(args):
    metadata, path, owner, study_name, reads_type, for_reads, rev_reads, barcodes, access_code = args
    with MetaDataUploader(metadata=metadata,
                          path=path,
                          study_type='qiime',
                          study_name=study_name,
                          reads_type=reads_type,
                          owner=fig.TEST_USER,
                          temporary=False,
                          public=False,
                          testing=True) as up:
        if rev_reads is None:
            access_code, email = up.import_metadata(for_reads=for_reads,
                                                    barcodes=barcodes,
                                                    access_code=access_code)
        else:
            access_code, email = up.import_metadata(for_reads=for_reads,
                                                    rev_reads=rev_reads,
                                                    barcodes=barcodes,
                                                    access_code=access_code)
        return access_code, email


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

        # If testing connect to test server
        if testing:
            # Connect as the specified user
            if user == sec.SQL_USER_NAME:
                self.db = pms.connect(host='localhost',
                                      user=sec.SQL_USER_NAME,
                                      password=sec.TEST_USER_PASS,
                                      database=SQL_DATABASE,
                                      local_infile=True)
            else:
                self.db = pms.connect(host='localhost',
                                      user='root',
                                      password=sec.TEST_ROOT_PASS,
                                      database=SQL_DATABASE,
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
                                      local_infile=True)
            else:
                self.db = pms.connect(host=sec.SQL_HOST,
                                      user=user,
                                      password=sec.SQL_ADMIN_PASS,
                                      database=sec.SQL_DATABASE,
                                      local_infile=True)
            self.mongo = men.connect(db=sec.MONGO_DATABASE,
                                     username=sec.MONGO_ADMIN_NAME,
                                     password=sec.MONGO_ADMIN_PASS,
                                     port=sec.MONGO_PORT,
                                     authentication_source=sec.MONGO_DATABASE,
                                     host=sec.MONGO_HOST)

        self.cursor = self.db.cursor()
        # Setup RLS for regular users
        if user == sec.SQL_USER_NAME:
            sql = 'SELECT set_connection_auth(%(owner)s, %(token)s)'
            self.cursor.execute(sql, {'owner': owner, 'token': sec.SECURITY_TOKEN})
            self.db.commit()

        # If the owner is None set user_id to 1
        if owner is None:
            self.user_id = 1
            self.email = MMEDS_EMAIL
        # Otherwise get the user id for the owner from the database
        else:
            sql = 'SELECT user_id, email FROM user WHERE user.username=%(uname)s'
            self.cursor.execute(sql, {'uname': owner})
            result = self.cursor.fetchone()
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
            self.cursor.execute(sql, {'token': sec.SECURITY_TOKEN})
            self.db.commit()
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
        sql = 'SELECT * FROM {table};'
        self.cursor.execute(quote_sql(sql, table=table))
        result = self.cursor.fetchall()
        table_text = '\n'.join(['\t'.join(['"{}"'.format(cell) for cell in row]) for row in result])
        return table_text

    def check_email(self, email):
        """ Check the provided email matches this user. """
        return email == self.email

    def get_email(self, username):
        """ Get the email that matches this user. """
        sql = 'SELECT `email` FROM `user` WHERE `username` = %(username)s'
        self.cursor.execute(sql, {'username': username})
        result = self.cursor.fetchone()
        if result is None:
            raise NoResultError('There is no entry for user {}'.format(username))
        return result[0]

    def get_privileges(self, username):
        """ Get the email that matches this user. """
        sql = 'SELECT `privilege` FROM `user` WHERE `username` = %(username)s'
        self.cursor.execute(sql, {'username': username})
        result = self.cursor.fetchone()
        if result is None:
            raise NoResultError('There is no entry for user {}'.format(username))
        return result[0]

    def get_hash_and_salt(self, username):
        """ Get the hash and salt values for the specified user. """
        sql = 'SELECT `password`, `salt` FROM `user` WHERE `username` = %(username)s'
        self.cursor.execute(sql, {'username': username})
        result = self.cursor.fetchone()
        if result is None:
            raise NoResultError('There is no entry for user {}'.format(username))
        return result

    def get_all_usernames(self):
        """ Return all usernames currently in the database. """
        sql = 'SELECT `username` FROM `user`'
        self.cursor.execute(sql)
        result = self.cursor.fetchall()
        if result is None:
            raise NoResultError('There are no users in the database')
        return [name[0] for name in result]

    def set_mmeds_user(self, user):
        """ Set the session to the current user of the webapp. """
        sql = 'SELECT set_connection_auth(%(user)s, %(token)s)'
        self.cursor.execute(sql, {'user': user, 'token': sec.SECURITY_TOKEN})
        set_user = self.cursor.fetchall()[0][0]
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

    def execute(self, sql):
        """ Execute the provided sql code """
        header = None
        # If the user is not an admin automatically map tables in the query
        # to their protected views
        if not self.user == 'root':
            for table in fig.PROTECTED_TABLES:
                if table in sql:
                    sql = sql.replace(' ' + table, ' protected_' + table)
                    sql = sql.replace(' `' + table, ' `protected_' + table)
                    sql = sql.replace('=`' + table, '=`protected_' + table)
                    sql = sql.replace('=' + table, '=protected_' + table)
        try:
            self.cursor.execute(sql)
            data = self.cursor.fetchall()
            if 'from' in sql.casefold():
                parsed = sql.split(' ')
                index = list(map(lambda x: x.casefold(), parsed)).index('from')
                table = parsed[index + 1]
                self.cursor.execute(quote_sql('DESCRIBE {table}', table=table))
                header = [x[0] for x in self.cursor.fetchall()]
        except pms.err.OperationalError as e:
            cp.log('OperationalError')
            cp.log(str(e))
            # If it's a select command denied error
            if e.args[0] == 1142:
                raise TableAccessError(e.args[1])
            raise e
        except (pms.err.ProgrammingError, pms.err.InternalError) as e:
            cp.log(str(e))
            data = str(e)
            raise InvalidSQLError(e.args[1])
        return data, header

    def purge(self):
        """
        Deletes every row from every table in the currently connected database.
        """
        self.cursor.execute('SHOW TABLES')
        tables = [x[0] for x in self.cursor.fetchall()]
        # Skip the user table
        tables.remove('user')
        r_tables = []
        while True:
            for table in tables:
                try:
                    self.cursor.execute(quote_sql('DELETE FROM {table}', table=table))
                    self.db.commit()
                except pms.err.IntegrityError:
                    r_tables.append(table)
            if not r_tables:
                break
            else:
                tables = r_tables
                r_tables = []

    def get_col_values_from_table(self, column, table):
        sql = quote_sql('SELECT {column} FROM {table}', column=column, table=table)
        self.cursor.execute(sql, {'column': column, 'table': table})
        data = self.cursor.fetchall()
        return data

    def add_user(self, username, password, salt, email, privilege_level):
        """ Add the user with the specified parameters. """
        self.cursor.execute('SELECT MAX(user_id) FROM user')
        user_id = int(self.cursor.fetchone()[0]) + 1
        # Create the SQL to add the user
        sql = 'INSERT INTO `user` (user_id, username, password, salt, email, privilege)'
        sql += ' VALUES (%(id)s, %(uname)s, %(pass)s, %(salt)s, %(email)s, %(privilege)s);'

        self.cursor.execute(sql, {'id': user_id,
                                  'uname': username,
                                  'pass': password,
                                  'salt': salt,
                                  'email': email,
                                  'privilege': privilege_level
                                  })
        self.db.commit()

    def remove_user(self, username):
        """ Remove a user from the database. """
        sql = 'DELETE FROM `user` WHERE username=%(uname)s'
        self.cursor.execute(sql, {'uname': username})
        self.db.commit()

    def clear_user_data(self, username):
        """
        Remove all data in the database belonging to username.
        ======================================================
        :username: The name of the user to remove files for
        """
        # Get the user_id for the provided username
        sql = 'SELECT user_id FROM `user` where username=%(uname)s'
        self.cursor.execute(sql, {'uname': username})
        user_id = int(self.cursor.fetchone()[0])

        # Only delete values from the tables that are protected
        tables = list(filter(lambda x: x in fig.PROTECTED_TABLES,
                             fig.TABLE_ORDER)) + fig.JUNCTION_TABLES
        # Start with the tables that link to other tables rather than one that are linked to
        tables.reverse()
        for table in tables:
            try:
                # Remove all values from the table belonging to that user
                sql = quote_sql('DELETE FROM {table} WHERE user_id=%(id)s', table=table)
                self.cursor.execute(sql, {'id': user_id})
            except pms.err.IntegrityError as e:
                # If there is a dependency remaining
                sql_log(e)
                sql_log('Failed on table {}'.format(table))
                raise MetaDataError(e.args[0])

        # Commit the changes
        self.db.commit()

        # Clear the mongo files
        self.clear_mongo_data(username)

    ########################################
    #               MongoDB                #
    ########################################
    @classmethod
    def create_access_code(cls, check_code, length=20):
        """ Creates a unique code for identifying a mongo db document """
        code = check_code
        count = 0
        while True:
            # Ensure no document exists with the given access code
            if not (StudyDoc.objects(access_code=code).first() or
                    AnalysisDoc.objects(access_code=code).first()):
                break
            else:
                code = check_code + '-' + str(count)
                count += 1
        return code

    def mongo_clean(self, access_code):
        obs = StudyDoc.objects(access_code=access_code)
        for ob in obs:
            ob.delete()
        obs = AnalysisDoc.objects(access_code=access_code)
        for ob in obs:
            ob.delete()

    def modify_data(self, new_data, access_code, data_type):
        """
        :new_data: A string or pathlike pointing to the location of the new data file.
        :access_code: The code for identifying this dataset.
        :data_type: A string. Either 'reads' or 'barcodes' depending on which is being modified.
        """
        mdata = StudyDoc.objects(access_code=access_code, owner=self.owner).first()
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
        new_code = get_salt(50)
        # Get the mongo document
        mdata = StudyDoc.objects(study=study_name, owner=self.owner, email=email).first()
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
        sql = 'SELECT * FROM user WHERE username = %(uname)s'
        self.cursor.execute(sql, {'uname': self.owner})
        result = self.cursor.fetchone()

        # Delete the old entry for the user
        sql = 'DELETE FROM user WHERE user_id = %(id)s'
        self.cursor.execute(sql, {'id': result[0]})

        # Insert the user with the updated password
        sql = 'INSERT INTO user (user_id, username, password, salt, email) VALUES\
            (%(id)s, %(uname)s, %(pass)s, %(salt)s, %(email)s);'
        self.cursor.execute(sql, {
            'id': result[0],
            'uname': result[1],
            'pass': new_password,
            'salt': new_salt,
            'email': result[4]
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
        sql_log('Update metadata with {}: {}'.format(filekey, value))
        mdata = StudyDoc.objects(access_code=access_code, owner=self.owner).first()
        mdata.last_accessed = datetime.utcnow()
        mdata.files[filekey] = value
        mdata.save()

    def check_repeated_subjects(self, df, subject_col=-2):
        """ Checks for users that match those already in the database. """
        warnings = []
        # If there is no subjects table in the metadata this
        # dataframe will be empty. If there are no subjects there
        # can't be any repeated subjects so it will just return the
        # empty list
        if not df.empty:
            # Go through each row
            for j in range(len(df.index)):
                sql = """SELECT * FROM Subjects WHERE"""
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
                    found = self.cursor.execute(sql, args)
                except pms.err.InternalError as e:
                    raise MetaDataError(e.args[1])
                if found >= 1:
                    sql_log(sql)
                    sql_log(args)
                    warning = '{row}\t{col}\tSubect in row {row} already exists in the database.'
                    warnings.append(warning.format(row=j, col=subject_col))
        return warnings

    def check_user_study_name(self, study_name):
        """ Checks if the current user has uploaded a study with the same name. """

        sql = 'SELECT * FROM Study WHERE user_id = %(id)s and Study.StudyName = %(study)s'
        log('Checking on user study')
        log('id: {}, studyName: {}'.format(self.user_id, study_name))
        log(sql)
        found = self.cursor.execute(sql, {'id': self.user_id, 'study': study_name})
        log(found)

        # Ensure multiple studies aren't uploaded with the same name
        if found >= 1 and not self.testing:
            result = ['-1\t-1\tUser {} has already uploaded a study with name {}'.format(self.owner, study_name)]
        else:
            result = []
        return result

    def get_mongo_files(self, access_code):
        """ Return mdata.files, mdata.path for the provided access_code. """
        mdata = StudyDoc.objects(access_code=access_code, owner=self.owner).first()

        # Raise an error if the upload does not exist
        if mdata is None:
            raise MissingUploadError()

        mdata.last_accessed = datetime.utcnow()
        mdata.save()
        return mdata.files, mdata.path

    def get_metadata(self, access_code):
        """
        Return the StudyDoc object.
        This object should be treated as read only.
        Any modifications should be done through the Database class.
        """
        return StudyDoc.objects(access_code=access_code, owner=self.owner).first()

    def get_analysis(self, access_code):
        """
        Return the StudyDoc object.
        This object should be treated as read only.
        Any modifications should be done through the Database class.
        """
        return AnalysisDoc.objects(access_code=access_code, owner=self.owner).first()

    @classmethod
    def get_all_studies(cls):
        """ Return all studies currently stored in the database. """
        return StudyDoc.objects()

    @classmethod
    def get_study(cls, access_code):
        """ Return all studies currently stored in the database. """
        return StudyDoc.objects(access_code=access_code).first()

    @classmethod
    def get_all_analyses_from_study(cls, access_code):
        """ Return all studies currently stored in the database. """
        return AnalysisDoc.objects(study_code=access_code)

    @classmethod
    def get_study_analysis(cls, access_code):
        """ Return all studies currently stored in the database. """
        return AnalysisDoc.objects(access_code=access_code).first()

    def check_files(self, access_code):
        """ Check that all files associated with the study actually exist. """
        mdata = StudyDoc.objects(access_code=access_code, owner=self.owner).first()
        empty_files = []
        for key in mdata.files.keys():
            if not os.path.exists(mdata.files[key]):
                empty_files.append(mdata.files[key])
                del mdata.files[key]
        return empty_files

    @classmethod
    def clear_mongo_data(cls, username):
        """ Clear all metadata documents associated with the provided username. """
        data = list(StudyDoc.objects(owner=username))
        data2 = list(AnalysisDoc.objects(owner=username))
        for doc in data + data2:
            doc.delete()

    def clean(self):
        """ Remove all temporary and intermediate files. """
        docs = StudyDoc.objects().first()
        if docs is None:
            return
        for mdata in docs:
            if (datetime.utcnow() - mdata.last_accessed).days > DAYS:
                for key in mdata.files.keys():
                    if key not in USER_FILES:
                        if os.path.isfile(mdata.files[key]):
                            os.remove(mdata.files[key])
                        elif os.path.exists(mdata.files[key]):
                            shutil.rmtree(mdata.files[key])

    @classmethod
    def get_mongo_docs(cls, access_code):
        """ For admin use """
        return (StudyDoc.objects(access_code=access_code),
                AnalysisDoc.objects(access_code=access_code))

    @classmethod
    def get_docs(cls, doc_type, access_code):
        """ For server use """
        if doc_type == 'analysis':
            docs = AnalysisDoc.objects(access_code=access_code)
        elif doc_type == 'study':
            docs = StudyDoc.objects(access_code=access_code)
        return docs


class SQLBuilder:
    def __init__(self, df, db, owner=None):
        """
        Handles creating an appropriate SQL query based on the information in df
        ---------------------------------------
        :df: A Pandas dataframe containing the parsed mmeds metadata to check against
        :db: A pymysql connection object.
        :owner: A string. The mmeds user account uploading or retrieving files.
        """
        warnings.simplefilter('ignore')

        self.owner = owner
        self.df = df
        self.row = None
        self.db = db
        self.cursor = self.db.cursor()

        # If the owner is None set user_id to 0
        if owner is None:
            self.user_id = 1
        # Otherwise get the user id for the owner from the database
        else:
            sql = 'SELECT user_id, email FROM user WHERE user.username=%(uname)s'
            self.cursor.execute(sql, {'uname': owner})
            result = self.cursor.fetchone()
            # Ensure the user exists
            if result is None:
                raise NoResultError('No account exists with the provided username and email.')
            self.user_id = int(result[0])

        self.check_file = fig.DATABASE_DIR / 'last_check.dat'

    def build_sql(self, table, row):
        """
            This function does the hard work of determining what a paticular table's
            entry should look like for a given row of the metadata file.
            ========================================================================
            :df: The dataframe containing the metadata to upload
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
        # Initialize the builder properties
        self.row = row
        return self.build_table_sql(table)

    def change_df(self, new_df):
        self.df = new_df

    def build_table_sql(self, table):
        """ Get the sql for a particular table. """

        # Get the columns for the specified table
        sql = 'DESCRIBE {}'.format(table)
        self.cursor.execute(sql)
        result = self.cursor.fetchall()
        all_cols = [res[0] for res in result]

        # Get all foreign keys present
        foreign_keys = list(filter(lambda x: '_has_' not in x,
                                   list(filter(lambda x: '_id' in x,
                                               all_cols))))
        # Get the non foreign key columns
        columns = list(filter(lambda x: '_id' not in x, all_cols))

        # Remove the user id
        if 'user_id' in foreign_keys:
            del foreign_keys[foreign_keys.index('user_id')]

        # Remove the table's primary key
        if 'id' + table in columns:
            del columns[columns.index('id' + table)]

        # Build the SQL for the Row and get the necessary foreign keys
        sql, args = self.create_query_from_row(table, columns)
        sql, args = self.add_foreign_keys(sql, args, foreign_keys)
        return sql, args

    def add_foreign_keys(self, sql, args, foreign_keys):
        """ Add necessary foreign keys to the provided query """
        # Collect the matching foreign keys based on the information
        # in the current row of the data frame
        for fkey in foreign_keys:
            ftable = fkey.split('_id')[1]
            # Recursively build the sql call
            fsql, fargs = self.build_table_sql(ftable)
            self.cursor.execute(fsql, fargs)
            try:
                # Get the resulting foreign key
                fresult = self.cursor.fetchone()[0]
            except TypeError as e:
                sql_log('ACCEPTED TYPE ERROR FINDING FOREIGN KEYS')
                sql_log(fsql)
                sql_log(fargs)
                raise e

            # Add it to the original query
            if '=' in sql or 'ISNULL' in sql:
                sql += ' AND '
            sql += quote_sql(('{fkey} = %({fkey})s'), fkey=fkey)
            args['`{}`'.format(fkey)] = pyformat_translate(fresult)
        return sql, args

    def create_query_from_row(self, table, columns):
        """ Creates an SQL query for the specified table from the provided dataframe """
        # Create an sql query to match the data from this row of the input file
        sql = quote_sql('SELECT * FROM {table} WHERE ', table=table)
        args = {}
        for i, column in enumerate(columns):
            value = self.df[table][column].iloc[self.row]
            if i == 0:
                sql += ' '
            else:
                sql += ' AND '
            if pd.isnull(value):  # Use NULL for NA values
                sql += quote_sql(('ISNULL({column})'), column=column)
            else:
                sql += quote_sql(('{column} = %({column})s'), column=column)
                args['`{}`'.format(column)] = pyformat_translate(value)
        # Add the user check for protected tables
        if table in fig.PROTECTED_TABLES:
            # user_id = 1 is the public user
            sql += ' AND (user_id = %(id)s OR user_id = 1)'
            args['id'] = self.user_id
        return sql, args


class MetaDataUploader:
    def __init__(self, metadata, path, owner, study_type, reads_type, study_name, temporary, public, testing=False):
        """
        Connect to the specified database.
        Initialize variables for this session.
        ---------------------------------------
        :metadata: A string. Path the metadata file to import.
        :path: A string. The path to the directory created for this session.
        :user: A string. What account to login to the SQL server with (user or admin).
        :owner: A string. The mmeds user account uploading or retrieving files.
        :testing: A boolean. Changes the connection parameters for testing.
        """
        warnings.simplefilter('ignore')

        self.path = Path(path) / 'database_files'
        self.IDs = defaultdict(dict)
        self.owner = owner
        self.testing = testing
        self.study_type = study_type
        self.reads_type = reads_type
        self.metadata = metadata
        self.study_name = study_name
        self.temporary = temporary
        self.public = public

        # If testing connect to test server
        if testing:
            self.db = pms.connect(host='localhost',
                                  user='root',
                                  password=sec.TEST_ROOT_PASS,
                                  database=SQL_DATABASE,
                                  autocommit=True,
                                  local_infile=True)
            # Connect to the mongo server
            self.mongo = men.connect(db='test',
                                     port=27017,
                                     host='127.0.0.1')
        # Otherwise connect to the deployment server
        else:
            self.db = pms.connect(host=sec.SQL_HOST,
                                  user=sec.SQL_ADMIN_NAME,
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

        if not temporary:
            # Read in the metadata file to import
            df = parse_ICD_codes(pd.read_csv(metadata, sep='\t', header=[0, 1], skiprows=[2, 3, 4]))
            self.df = df.reindex(df.columns, axis=1)
            self.builder = SQLBuilder(self.df, self.db, owner)

        # If the owner is None set user_id to 0
        if owner is None:
            self.user_id = 0
            self.email = MMEDS_EMAIL
        # Otherwise get the user id for the owner from the database
        else:
            sql = 'SELECT user_id, email FROM user WHERE user.username=%(uname)s'
            cursor = self.db.cursor()
            cursor.execute(sql, {'uname': owner})
            result = cursor.fetchone()
            cursor.close()
            # Ensure the user exists
            if result is None:
                raise NoResultError('No account exists with the provided username and email.')
            self.user_id = int(result[0])
            self.email = result[1]

        # If the metadata is to be made public overwrite the user_id
        if public:
            self.user_id = 1
        self.check_file = fig.DATABASE_DIR / 'last_check.dat'

    def __del__(self):
        """ Clear the current user session and disconnect from the database. """
        self.db.close()

    def __enter__(self):
        """ Allows database connection to be used via a 'with' statement. """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Delete the Database instance upon the end of the 'with' block. """
        del self

    def import_metadata(self, **kwargs):
        """
        Creates table specific input csv files from the complete metadata file.
        Imports each of those files into the database.
        """
        access_code = None

        if not self.path.is_dir():
            self.path.mkdir()

        # Import the files into the mongo database
        access_code = self.mongo_import(**kwargs)

        # If the metadata file is not temporary perform the import into the SQL database
        if not self.temporary:
            # Sort the available tables based on TABLE_ORDER
            columns = self.df.columns.levels[0].tolist()
            column_order = [TABLE_ORDER.index(col) for col in columns]
            tables = [x for _, x in sorted(zip(column_order, columns)) if not x == 'ICDCode']

            # Create file and import data for each regular table
            for table in tables:
                # Upload the additional meta data to the NoSQL database
                if not table == 'AdditionalMetaData':
                    self.create_import_data(table)
                    filename = self.create_import_file(table)

                    if isinstance(filename, WindowsPath):
                        filename = str(filename).replace('\\', '\\\\')
                    # Load the newly created file into the database
                    sql = quote_sql('LOAD DATA LOCAL INFILE %(file)s INTO TABLE {table} FIELDS TERMINATED BY "\\t"',
                                    table=table)
                    sql += ' LINES TERMINATED BY "\\n" IGNORE 1 ROWS'
                    cursor = self.db.cursor()
                    cursor.execute(sql, {'file': str(filename), 'table': table})
                    cursor.close()
                    # Commit the inserted data
                    self.db.commit()

            # Create csv files and import them for
            # each junction table
            self.fill_junction_tables()

            # Remove all row information from the current input
            self.IDs.clear()

        return access_code, self.email

    def create_import_data(self, table, verbose=True):
        """
        Fill out the dictionaries used to create the input files
        from the input data file.
        :table: The table in the database to create the import data for
        :df: The dataframe containing all the metadata
        """
        sql = quote_sql('SELECT MAX({idtable}) FROM {table}', idtable='id' + table, table=table)

        cursor = self.db.cursor()
        cursor.execute(sql)
        vals = cursor.fetchone()
        cursor.close()
        try:
            current_key = int(vals[0]) + 1
        except TypeError:
            current_key = 1
        # Track keys for repeated values in this file
        seen = {}

        # Go through each row
        for row in range(len(self.df.index)):
            sql, args = self.builder.build_sql(table, row)
            sql_log(sql)
            sql_log(args)
            # Get any foreign keys which can also make this row unique
            fkeys = ['{}={}'.format(key, value) for key, value in args.items() if '_id' in key]
            # Create the entry
            this_row = ''.join(list(map(str, self.df[table].iloc[row])) + fkeys)
            try:
                # See if this table entry already exists in the current input file
                key = seen[this_row]
                self.IDs[table][row] = key
            except KeyError:
                cursor = self.db.cursor()
                found = cursor.execute(sql, args)
                if found >= 1:
                    # Append the key found for that column
                    result = cursor.fetchone()
                    self.IDs[table][row] = int(result[0])
                    seen[this_row] = int(result[0])
                else:
                    # If not add it and give it a unique key
                    seen[this_row] = current_key
                    self.IDs[table][row] = current_key
                    current_key += 1
                cursor.close()

    def create_import_line(self, table, structure, columns, row_index):
        """
        Creates a single line of the input file for the specified metadata table
        :table: The name of the table the input is for
        :structure: ...
        :columns: ...
        :row_index: ...
        """
        line = []
        # For each column in the table
        for j, col in enumerate(columns):
            # If the column is a primary key or foreign key
            if structure[j][3] == 'PRI' or structure[j][3] == 'MUL':
                key_table = col.split('id')[-1]
                # Get the approriate data from the dictionary
                try:
                    line.append(self.IDs[key_table][row_index])
                except KeyError:
                    raise KeyError('Error getting key self.IDs[{}][{}]'.format(key_table, row_index))
            elif structure[j][0] == 'user_id':
                line.append(str(self.user_id))
            elif structure[j][0] == 'AdditionalMetaDataRow':
                line.append(str(row_index))
            else:
                # Otherwise see if the entry already exists
                try:
                    if pd.isnull(self.df[table].loc[row_index][col]):
                        line.append('\\N')
                    else:
                        line.append(self.df[table].loc[row_index][col])
                except KeyError:
                    line.append(col)
        return line

    def create_import_file(self, table):
        """
        Create the file to load into each table referenced in the
        metadata input file
        """
        # Get the structure of the table currently being filled out

        cursor = self.db.cursor()
        cursor.execute('DESCRIBE ' + table)
        structure = cursor.fetchall()
        cursor.close()
        # Get the columns for the table
        columns = list(map(lambda x: x[0], structure))
        filename = self.path / (table + '_input.csv')
        # Create the input file
        with open(filename, 'w') as f:
            f.write('\t'.join(columns) + '\n')
            # For each row in the input file
            for i in range(len(self.df.index)):
                line = self.create_import_line(table, structure, columns, i)
                f.write('\t'.join(list(map(str, line))) + '\n')
        return filename

    def fill_junction_tables(self):
        """
        Create and load the import files for every junction table.
        """
        # Import data for each junction table
        for table in fig.JUNCTION_TABLES:
            sql = quote_sql('DESCRIBE {table};', table=table)

            cursor = self.db.cursor()
            cursor.execute(sql)
            result = cursor.fetchall()
            cursor.close()
            columns = list(map(lambda x: x[0].split('_')[0], result))
            key_pairs = []
            # Only fill in tables where both foreign keys exist
            try:
                # Get the appropriate foreign keys from the IDs dict
                for key in self.IDs[columns[0]].keys():
                    keys_list = []
                    # Ignore user_id column
                    for column in columns[:-1]:
                        keys_list.append(str(self.IDs[column][key]))
                    # Add user_id
                    keys_list.append(str(self.user_id))
                    key_pairs.append('\t'.join(keys_list) + '\n')

                # Remove any repeated pairs of foreign keys
                unique_pairs = list(set(key_pairs))
                filename = self.path / (table + '_input.csv')

                # Create the input file for the juntion table
                with open(filename, 'w') as f:
                    f.write('\t'.join(columns) + '\n')
                    for pair in unique_pairs:
                        f.write(pair)

                if isinstance(filename, WindowsPath):
                    filename = str(filename).replace('\\', '\\\\')

                # Load the datafile in to the junction table
                sql = quote_sql('LOAD DATA LOCAL INFILE %(file)s INTO TABLE {table} FIELDS TERMINATED BY "\\t"',
                                table=table)
                sql += ' LINES TERMINATED BY "\\n" IGNORE 1 ROWS'
                cursor = self.db.cursor()
                cursor.execute(sql, {'file': str(filename), 'table': table})
                cursor.close()
                # Commit the inserted data
                self.db.commit()
            except KeyError as e:
                e.args[1] += '\t{}\n'.format(str(filename))
                raise e

    def mongo_import(self, **kwargs):
        """ Imports additional columns into the NoSQL database. """
        # If an access_code is provided use that
        # For testing purposes
        if kwargs.get('access_code') is not None:
            access_code = kwargs.get('access_code')
        else:
            access_code = get_salt(50)

        # Create the document
        mdata = StudyDoc(created=datetime.utcnow(),
                         last_accessed=datetime.utcnow(),
                         testing=self.testing,
                         study_type=self.study_type,
                         reads_type=self.reads_type,
                         study=self.study_name,
                         access_code=access_code,
                         owner=self.owner,
                         email=self.email,
                         public=self.public,
                         path=str(self.path.parent))

        # Add the files approprate to the type of study
        mdata.files.update(kwargs)
        mdata.files['metadata'] = self.metadata

        # Save the document
        mdata.save()
        return access_code
