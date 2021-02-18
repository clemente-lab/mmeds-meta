import os
import warnings

import mmeds.secrets as sec
import mmeds.config as fig
import mmeds.formatter as fmt
import mongoengine as men
import pymysql as pms
import cherrypy as cp
import pandas as pd

from datetime import datetime
from pathlib import Path
from prettytable import PrettyTable, ALL
from collections import defaultdict
from mmeds.error import (TableAccessError, MissingUploadError, MissingFileError, StudyNameError,
                         MetaDataError, NoResultError, InvalidSQLError)
from mmeds.util import (send_email, pyformat_translate, quote_sql)
from mmeds.database.metadata_uploader import MetaDataUploader
from mmeds.documents import MMEDSDoc
from mmeds.logging import Logger

DAYS = 13


# Used in test_cases
def upload_metadata(args):
    (subject_metadata, subject_type, specimen_metadata, path, owner, study_name,
     reads_type, barcodes_type, for_reads, rev_reads, barcodes, access_code, testing) = args
    if for_reads is not None and 'zip' in for_reads:
        datafiles = {'data': for_reads,
                     'barcodes': barcodes}
    else:
        datafiles = {'for_reads': for_reads,
                     'rev_reads': rev_reads,
                     'barcodes': barcodes}
    p = MetaDataUploader(subject_metadata, subject_type, specimen_metadata, owner, 'qiime', reads_type,
                         barcodes_type, study_name, False, datafiles, False, testing, access_code)
    return p.run()


def upload_otu(args):
    (subject_metadata, subject_type, specimen_metadata, path, owner, study_name, otu_table, access_code) = args
    datafiles = {'otu_table': otu_table}
    p = MetaDataUploader(subject_metadata, subject_type, specimen_metadata, owner, 'sparcc', 'otu_table',
                         None, study_name, False, datafiles, False, True, access_code)
    p.run()
    return 0


def upload_lefse(args):
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

        # If testing connect to test server
        if testing:
            # Connect as the specified user
            if user == sec.SQL_USER_NAME:
                self.db = pms.connect(host='localhost',
                                      user=sec.SQL_USER_NAME,
                                      password=sec.TEST_USER_PASS,
                                      database=fig.SQL_DATABASE,
                                      local_infile=True)
            else:
                self.db = pms.connect(host='localhost',
                                      user='root',
                                      password=sec.TEST_ROOT_PASS,
                                      database=fig.SQL_DATABASE,
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

        MMEDSDoc.objects.timeout(False)
        self.cursor = self.db.cursor()
        # Setup RLS for regular users
        if user == sec.SQL_USER_NAME:
            sql = 'SELECT set_connection_auth(%(owner)s, %(token)s)'
            self.cursor.execute(sql, {'owner': owner, 'token': sec.SECURITY_TOKEN})
            self.db.commit()

        # If the owner is None set user_id to 1
        if owner is None:
            self.user_id = 1
            self.email = fig.MMEDS_EMAIL
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

    def build_html_table(self, header, data):
        """
        Return an HTML formatted table containing the results of the provided query
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

    @classmethod
    def format_results(cls, header, data):
        """ Takes the results from a query and formats them into a python dict """
        formatted = defaultdict(list)
        for row in data:
            for column, value in zip(header, row):
                formatted[column].append(value)
        return formatted

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
        if not self.user == sec.SQL_ADMIN_NAME:
            # Replace references to protected tables to their view counterparts
            for table in fig.PROTECTED_TABLES:
                if table in sql:
                    sql = sql.replace(' ' + table, ' protected_' + table)
                    sql = sql.replace(' `' + table, ' `protected_' + table)
                    sql = sql.replace('=`' + table, '=`protected_' + table)
                    sql = sql.replace('=' + table, '=protected_' + table)
        try:
            # Get the table column headers
            if 'from' in sql.casefold():
                parsed = sql.split(' ')
                index = list(map(lambda x: x.casefold(), parsed)).index('from')
                table = parsed[index + 1]
                self.cursor.execute(quote_sql('DESCRIBE {table}', table=table))
                header = [x[0] for x in self.cursor.fetchall()]
                if filter_ids:
                    # Remove foreign keys
                    header = [col for col in header if 'id' not in col]
                    # Expand * to limit results
                    sql = sql.replace('*', ', '.join(header))

            self.cursor.execute(sql)
            data = self.cursor.fetchall()
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

    def delete_sql_rows(self):
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
                Logger.info(e)
                Logger.info('Failed on table {}'.format(table))
                raise MetaDataError(e.args[0])

        # Commit the changes
        self.db.commit()

        # Clear the mongo files
        self.clear_mongo_data(username)

    def generate_id(self, access_code, study_name, specimen_id, aliquot_weight):
        """ Generate a new id for the aliquot with the given weight """

        # Get a new unique SQL id for this aliquot
        self.cursor.execute("SELECT MAX(idAliquot) from Aliquot")
        idAliquot = self.cursor.fetchone()[0] + 1

        # Get the SQL id of the Specimen this should be associated with
        data, header = self.execute(fmt.GET_SPECIMEN_QUERY.format(column='idSpecimen',
                                                                  study_name=study_name,
                                                                  specimen_id=specimen_id), False)
        idSpecimen = data[0][0]
        # Get the number of Aliquots previously created from this Specimen
        self.cursor.execute(f'SELECT COUNT(AliquotID) FROM Aliquot WHERE Specimen_idSpecimen = "{idSpecimen}"')
        aliquot_count = self.cursor.fetchone()[0]

        # Create the human readable ID
        AliquotID = '{}-Aliquot{}'.format(specimen_id, aliquot_count)

        # Get the user ID
        self.cursor.execute(fmt.GET_SPECIMEN_QUERY.format(column='Specimen.user_id',
                                                          study_name=study_name,
                                                          specimen_id=specimen_id))
        user_id = self.cursor.fetchone()[0]

        row_string = f'({idAliquot}, {idSpecimen}, {user_id}, "{AliquotID}", {aliquot_weight})'
        sql = fmt.INSERT_ALIQUOT_QUERY.format(row_string)
        self.cursor.execute(sql)
        return AliquotID

    ########################################
    #               MongoDB                #
    ########################################
    @classmethod
    def create_access_code(cls, check_code=None, length=20):
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
                initial_sql = """SELECT * FROM Subjects WHERE"""
            elif subject_type == 'animal':
                initial_sql = """SELECT * FROM AnimalSubjects WHERE"""
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
                    found = self.cursor.execute(sql, args)
                except pms.err.InternalError as e:
                    raise MetaDataError(e.args[1])
                if found >= 1:
                    Logger.info(sql)
                    Logger.info(args)
                    warning = '{row}\t{col}\tSubject in row {row} already exists in the database.'
                    warnings.append(warning.format(row=j, col=subject_col))
        return warnings

    def check_user_study_name(self, study_name):
        """ Checks if the current user has uploaded a study with the same name. """

        sql = 'SELECT * FROM Study WHERE user_id = %(id)s and Study.StudyName = %(study)s'
        found = self.cursor.execute(sql, {'id': self.user_id, 'study': study_name})

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
                raise MissingFileError('File {}, does not exist')

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

    def get_study(self, access_code, check_owner=True):
        """
        Return the MMEDSDoc object.
        This object should be treated as read only.
        Any modifications should be done through the Database class.
        """
        if check_owner:
            doc = MMEDSDoc.objects(study_code=str(access_code), owner=self.owner).first()
        else:
            doc = MMEDSDoc.objects(access_code=str(access_code)).first()
        if doc is None:
            raise MissingUploadError('Upload does not exist for user {} with code {}'.format(self.owner, access_code))
        return doc

    def get_doc(self, access_code, check_owner=True):
        """
        Return the MMEDSDoc object.
        This object should be treated as read only.
        Any modifications should be done through the Database class.
        """
        if check_owner:
            doc = MMEDSDoc.objects(access_code=str(access_code), owner=self.owner).first()
        else:
            doc = MMEDSDoc.objects(access_code=str(access_code)).first()
        if doc is None:
            raise MissingUploadError('Upload does not exist for user {} with code {}'.format(self.owner, access_code))
        return doc

    def check_upload(self, access_code):
        obs = MMEDSDoc.objects(access_code=access_code, owner=self.owner)
        if not obs:
            raise MissingUploadError()

    def check_study_name(self, study_name):
        """ Verifies the provided study name is valid and not already in use. """
        if not study_name.replace('_', '').isalnum():
            raise StudyNameError("Only alpha numeric characters and '_' are allowed in the study name")
        if MMEDSDoc.objects(study_name=study_name):
            raise StudyNameError(f"Study name {study_name} already in use")

    @classmethod
    def get_all_studies(cls):
        """ Return all studies currently stored in the database. """
        return MMEDSDoc.objects(doc_type='study')

    @classmethod
    def get_all_analyses(cls):
        """ Return all analyses currently stored in the database. """
        return MMEDSDoc.objects(doc_type='analysis')

    @classmethod
    def get_all_user_studies(cls, user):
        """ Return all studies currently stored in the database owned by USER. """
        return MMEDSDoc.objects(doc_type='study', owner=user)

    @classmethod
    def get_all_analyses_from_study(cls, access_code):
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

    @classmethod
    def delete_mongo_documents(cls):
        """ Clear all metadata documents associated with the provided username. """
        data = list(MMEDSDoc.objects())
        for doc in data:
            doc.delete()

    def clear_mongo_data(self, username):
        """ Clear all metadata documents associated with the provided username. """
        data = list(MMEDSDoc.objects(owner=username))
        for doc in data:
            doc.delete()

    @classmethod
    def get_docs(cls, **kwargs):
        """ For server use """
        return MMEDSDoc.objects(**kwargs)
