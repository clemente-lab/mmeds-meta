import pymysql as pms
import mongoengine as men
import cherrypy as cp
import pandas as pd
import os
import shutil
import pickle
import warnings

from datetime import datetime
from pathlib import WindowsPath, Path
from prettytable import PrettyTable, ALL
from collections import defaultdict
from mmeds.config import SQL_DATABASE, SECURITY_TOKEN, TABLE_ORDER, MMEDS_EMAIL, USER_FILES, STORAGE_DIR, get_salt
from mmeds.error import TableAccessError, MissingUploadError, MetaDataError
from mmeds.mmeds import send_email

DAYS = 13


class MetaData(men.DynamicDocument):
    created = men.DateTimeField()
    last_accessed = men.DateTimeField()
    study_type = men.StringField(max_length=45, required=True)
    study = men.StringField(max_length=45, required=True)
    access_code = men.StringField(max_length=50, required=True)
    owner = men.StringField(max_length=100, required=True)
    email = men.StringField(max_length=100, required=True)
    path = men.StringField(max_length=100, required=True)
    files = men.DictField()

    # When the document is updated record the
    # location of all files in a new file
    def save(self):
        with open(str(Path(self.path) / 'file_index.tsv'), 'w') as f:
            f.write('Key\tPath\n')
            for key in self.files:
                f.write('{}\t{}\n'.format(key, self.files[key]))
        super(MetaData, self).save()


class Database:

    def __init__(self, path, database=SQL_DATABASE, user='root', owner=None, connect=True, testing=False):
        """
        Connect to the specified database.
        Initialize variables for this session.
        """
        warnings.simplefilter('ignore')
        try:
            if user == 'mmeds_user':
                self.db = pms.connect('localhost', user, 'password', database, max_allowed_packet=2048000000, local_infile=True)
            else:
                self.db = pms.connect('localhost', user, '', database, max_allowed_packet=2048000000, local_infile=True)
        except pms.err.ProgrammingError as e:
            cp.log('Error connecting to ' + database)
            raise e
        self.mongo = men.connect('test', host='127.0.0.1', port=27017, connect=connect)
        self.path = path
        self.IDs = defaultdict(dict)
        self.cursor = self.db.cursor()
        if user == 'mmeds_user':
            sql = 'SELECT set_connection_auth("{}", "{}")'.format(owner, SECURITY_TOKEN)
            self.cursor.execute(sql)
            self.db.commit()
        self.owner = owner
        if owner is None:
            self.user_id = 0
            self.email = MMEDS_EMAIL
        else:
            sql = 'SELECT user_id, email FROM user WHERE user.username="' + owner + '"'
            self.cursor.execute(sql)
            result = self.cursor.fetchone()
            self.user_id = int(result[0])
            self.email = result[1]

        self.check_file = STORAGE_DIR / 'last_check.dat'

        if not testing:
            # Do housekeeping for removing old files
            if os.path.isfile(self.check_file):
                with open(self.check_file, 'rb') as f:
                    last_check = pickle.load(f)
                if (datetime.utcnow() - last_check).days > DAYS:
                    self.clean()
                    with open(self.check_file, 'wb') as f:
                        pickle.dump(datetime.utcnow(), f)
            else:
                with open(self.check_file, 'wb+') as f:
                    pickle.dump(datetime.utcnow(), f)

    def __del__(self):
        """ Clear the current user session and disconnect from the database. """
        sql = 'SELECT unset_connection_auth("{}")'.format(SECURITY_TOKEN)
        self.cursor.execute(sql)
        self.db.commit()
        self.db.close()

    def __enter__(self):
        """ Allows database connection to be used via a 'with' statement. """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Delete the Database instance upon the end of the 'with' block. """
        del self

    ########################################
    ###############  MySQL  ################
    ########################################

    def check_email(self, email):
        """ Check the provided email matches this user. """
        return email == self.email

    def get_email(self):
        """ Check the provided email matches this user. """
        return self.email

    def set_mmeds_user(self, user):
        """ Set the session to the current user of the webapp. """
        sql = 'SELECT set_connection_auth("{}", "{}")'.format(user, SECURITY_TOKEN)
        self.cursor.execute(sql)
        set_user = self.cursor.fetchall()[0][0]
        self.db.commit()
        return set_user

    def format(self, text, header=None):
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
        try:
            self.cursor.execute(sql)
            data = self.cursor.fetchall()
            header = None
            if 'from' in sql.casefold():
                parsed = sql.split(' ')
                index = list(map(lambda x: x.casefold(), parsed)).index('from')
                table = parsed[index + 1]
                self.cursor.execute('describe ' + table)
                header = [x[0] for x in self.cursor.fetchall()]
            return data, header
        except pms.err.OperationalError as e:
            # If it's a select command denied error
            if e.args[0] == 1142:
                raise TableAccessError(e.args[1])
            else:
                raise e
        except pms.err.ProgrammingError as e:
            cp.log('Error executing SQL command: ' + sql)
            cp.log(str(e))
            return str(e), header

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
                    self.cursor.execute('DELETE FROM ' + table)
                    self.db.commit()
                except pms.err.IntegrityError:
                    r_tables.append(table)
            if len(r_tables) == 0:
                break
            else:
                tables = r_tables
                r_tables = []

    def check_file_header(self, fp, delimiter='\t'):
        """
        UNFINISHED
        Checks that the metadata input file doesn't contain any
        tables or columns that don't exist in the database.
        df = pd.read_csv(fp, sep=delimiter, header=[0, 1], nrows=2)
        self.cursor.execute('SHOW TABLES')
        tables = list(filter(lambda x: '_' not in x,
                             [l[0] for l in self.cursor.fetchall()]))

        # Import data for each junction table
        for table in tables:
            self.cursor.execute('DESCRIBE ' + table)
            columns = list(map(lambda x: x[0].split('_')[0],
                               self.cursor.fetchall()))
        """
        pass

    def create_import_data(self, table, df, verbose=True):
        """
        Fill out the dictionaries used to create the input files
        from the input data file.
        """
        sql = 'SELECT COUNT(*) FROM ' + table
        self.cursor.execute(sql)
        current_key = int(self.cursor.fetchone()[0])
        # Track keys for repeated values in this file
        seen = {}
        # Go through each column
        for j in range(len(df.index)):
            sql = 'SELECT * FROM ' + table + ' WHERE'
            # Check if there is a matching entry already in the database
            for i, column in enumerate(df[table]):
                value = df[table][column][j]
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
                sql += ' AND user_id = ' + str(self.user_id)
            found = self.cursor.execute(sql)
            if found == 1:
                # Append the key found for that column
                result = self.cursor.fetchone()
                self.IDs[table][j] = int(result[0])
            else:
                # Create the entry
                this_row = ''.join(list(map(str, df[table].loc[j])))
                try:
                    # See if this table entry already exists in the current input file
                    key = seen[this_row]
                    self.IDs[table][j] = key
                except KeyError:
                    # If not add it and give it a unique key
                    seen[this_row] = current_key
                    self.IDs[table][j] = current_key
                    current_key += 1

    def create_import_line(self, df, table, structure, columns, row_index):
        line = []
        # For each column in the table
        for j, col in enumerate(columns):

            # If the column is a primary key
            if structure[j][3] == 'PRI':
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
                    if pd.isnull(df[table].loc[row_index][col]):
                        line.append('NULL')
                    else:
                        line.append(df[table].loc[row_index][col])
                except KeyError:
                    line.append(col)
        return line

    def create_import_file(self, table, df):
        """
        Create the file to load into each table referenced in the
        metadata input file
        """
        # Get the structure of the table currently being filled out
        self.cursor.execute('DESCRIBE ' + table)
        structure = self.cursor.fetchall()
        # Get the columns for the table
        columns = list(map(lambda x: x[0], structure))
        filename = self.path / (table + '_input.csv')
        # Create the input file
        with open(filename, 'w') as f:
            f.write('\t'.join(columns) + '\n')
            # For each row in the input file
            for i in range(len(df.index)):
                line = self.create_import_line(df,
                                               table,
                                               structure,
                                               columns,
                                               i)
                f.write('\t'.join(list(map(str, line))) + '\n')
        return filename

    def fill_junction_tables(self):
        """
        Create and load the import files for every junction table.
        """
        self.cursor.execute('SHOW TABLES')
        tables = list(filter(lambda x: '_has_' in x,
                             [l[0] for l in self.cursor.fetchall()]))
        # Import data for each junction table
        for table in tables:
            sql = 'DESCRIBE ' + table
            self.cursor.execute(sql)
            columns = list(map(lambda x: x[0].split('_')[0],
                               self.cursor.fetchall()))
            key_pairs = []
            # Only fill in tables where both foreign keys exist
            try:
                # Get the appropriate foreign keys from the IDs dict
                for key in self.IDs[columns[0]].keys():
                    keys_list = []
                    for column in columns:
                        keys_list.append(str(self.IDs[column][key]))
                    key_pairs.append('\t'.join(keys_list) + '\n')

                # Remove any repeated pairs of foreign keys
                unique_pairs = list(set(key_pairs))
                filename = self.path / (table + '_input.csv')

                # Create the input file for the juntion table
                with open(filename, 'w') as f:
                    f.write(columns[0] + '\t' + columns[1] + '\n')
                    for pair in unique_pairs:
                        f.write(pair + '\n')

                if isinstance(filename, WindowsPath):
                    filename = str(filename).replace('\\', '\\\\')

                # Load the datafile in to the junction table
                sql = 'LOAD DATA LOCAL INFILE "' + str(filename) + '" INTO TABLE ' +\
                      table + ' FIELDS TERMINATED BY "\\t"' +\
                      ' LINES TERMINATED BY "\\n" IGNORE 1 ROWS'
                self.cursor.execute(sql)
                # Commit the inserted data
                self.db.commit()
            except KeyError as e:
                e.args[1] += '\t{}\n'.format(str(filename))
                raise e

    def read_in_sheet(self, metadata, study_type, delimiter='\t', **kwargs):
        """
        Creates table specific input csv files from the complete metadata file.
        Imports each of those files into the database.
        """
        access_code = None

        # Read in the metadata file to import
        df = pd.read_csv(metadata, sep=delimiter, header=[0, 1])
        df = df.reindex_axis(df.columns, axis=1)
        study_name = df['Study']['StudyName'][0]
        sql = 'SET FOREIGN_KEY_CHECKS=0'
        self.cursor.execute(sql)
        self.db.commit()

        tables = df.columns.levels[0].tolist()
        tables.sort(key=lambda x: TABLE_ORDER.index(x))

        # Create file and import data for each regular table
        for table in tables:
            # Upload the additional meta data to the NoSQL database
            if table == 'AdditionalMetaData':
                kwargs['metadata'] = metadata
                access_code = self.mongo_import(study_name, study_type, **kwargs)
            else:
                self.create_import_data(table, df)
                filename = self.create_import_file(table, df)

                if isinstance(filename, WindowsPath):
                    filename = str(filename).replace('\\', '\\\\')
                # Load the newly created file into the database
                sql = 'LOAD DATA LOCAL INFILE "' + str(filename) + '" INTO TABLE ' +\
                      table + ' FIELDS TERMINATED BY "\\t"' +\
                      ' LINES TERMINATED BY "\\n" IGNORE 1 ROWS'
                self.cursor.execute(sql)
                # Commit the inserted data
                self.db.commit()

        # Create csv files and import them for
        # each junction table
        self.fill_junction_tables()

        # Remove all row information from the current input
        self.IDs.clear()

        return access_code, study_name, self.email

    def get_col_values_from_table(self, column, table):
        sql = 'SELECT {} FROM {}'.format(column, table)
        self.cursor.execute(sql)
        data = self.cursor.fetchall()
        return data

    def add_user(self, username, password, salt, email):
        """ Add the user with the specified parameters. """
        # Create the SQL to add the user
        sql = 'INSERT INTO mmeds.user (username, password, salt, email) VALUES\
                ("{}", "{}", "{}", "{}");'.format(username, password, salt, email)

        self.cursor.execute(sql)
        self.db.commit()

    def remove_user(self, username):
        """ Remove a user from the database. """
        sql = 'DELETE FROM mmeds.user WHERE username="{}"'.format(username)
        self.cursor.execute(sql)
        self.db.commit()

    def clear_user_data(self, username):
        """
        Remove all data in the database belonging to username.

        DOES NOT WORK

        """
        return
        sql = 'SELECT user_id FROM mmeds.user where username="{}"'.format(username)
        self.cursor.execute(sql)
        user_id = int(self.cursor.fetchone()[0])
        print(user_id)

        self.cursor.execute('SHOW TABLES')
        tables = [x[0] for x in self.cursor.fetchall()]
        # Skip the user table
        tables.remove('user')
        r_tables = []
        while True:
            for table in tables:
                try:
                    sql = 'DESCRIBE {}'.format(table)
                    self.cursor.execute(sql)
                    columns = self.cursor.fetchall()
                    labels = [col[0] for col in columns]
                    if 'user_id' in labels:
                        sql = 'DELETE FROM {} WHERE user_id={}'.format(table, user_id)
                        print(sql)
                        self.cursor.execute(sql)
                        self.db.commit()
                    else:
                        continue
                except pms.err.IntegrityError:
                    r_tables.append(table)
            if len(r_tables) == 0:
                break
            else:
                tables = r_tables
                r_tables = []

    ########################################
    ##############  MongoDB  ###############
    ########################################

    def mongo_import(self, study_name, study_type, **kwargs):
        """ Imports additional columns into the NoSQL database. """
        # If an access_code is provided use that
        # For testing purposes
        if kwargs.get('access_code') is not None:
            access_code = kwargs.get('access_code')
        else:
            access_code = get_salt(50)
        # Create the document
        mdata = MetaData(created=datetime.utcnow(),
                         last_accessed=datetime.utcnow(),
                         study_type=study_type,
                         study=study_name,
                         access_code=access_code,
                         owner=self.owner,
                         email=self.email,
                         path=str(self.path))

        # Add the files approprate to the type of study
        mdata.files.update(kwargs)

        # Save the document
        mdata.save()
        return access_code

    def mongo_clean(self, access_code):
        """
        Delete all mongo objects with the given access_code.
        It will not delete the files associated with those objects.
        """

        obs = MetaData.object(access_code=access_code)
        for ob in obs:
            ob.delete()

    def modify_data(self, new_data, access_code):
        mdata = MetaData.objects(access_code=access_code, owner=self.owner).first()
        mdata.last_accessed = datetime.utcnow()
        # Open the data file
        with open(new_data, 'rb') as data_file:
            mdata.data.replace(data_file)
            mdata.save()

    def reset_access_code(self, study_name, email):
        """
        Reset the access_code for the study with the matching name and email.
        """
        # Get a new code
        new_code = get_salt(50)
        # Get the mongo document
        mdata = MetaData.objects(study=study_name, owner=self.owner, email=email).first()
        mdata.last_accessed = datetime.utcnow()
        mdata.access_code = new_code
        mdata.save()
        send_email(email, self.owner, new_code)

    def change_password(self, new_password, new_salt):
        """ Change the password for the current user. """
        # Get the user's information from the user table
        sql = 'SELECT * FROM user WHERE username = "{}"'.format(self.owner)
        self.cursor.execute(sql)
        result = self.cursor.fetchone()
        # Ensure the user exists
        if len(result) == 0:
            return False

        # Delete the old entry for the user
        sql = 'DELETE FROM user WHERE user_id = {}'.format(result[0])
        self.cursor.execute(sql)

        # Insert the user with the updated password
        sql = 'INSERT INTO mmeds.user (user_id, username, password, salt, email) VALUES\
                ({}, "{}", "{}", "{}", "{}");'.format(result[0],
                                                      result[1],
                                                      new_password,
                                                      new_salt,
                                                      result[4])
        self.cursor.execute(sql)
        self.db.commit()
        return True

    def update_metadata(self, access_code, filekey, filename):
        """
        Add a file to a metadata object
        ====================================
        :access_code: Code identifiying the document to update
        :filekey: The key the new file should be indexed under
        :filename: The path to the new file
        """
        mdata = MetaData.objects(access_code=access_code, owner=self.owner).first()
        mdata.last_accessed = datetime.utcnow()
        mdata.files[filekey] = str(self.path / filename)
        mdata.save()

    def check_repeated_subjects(self, df, subject_col=-2):
        """ Checks for users that match those already in the database. """
        warnings = []
        # Go through each column
        for j in range(len(df.index)):
            sql = 'SELECT * FROM Subjects WHERE'
            # Check if there is a matching entry already in the database
            for i, column in enumerate(df):
                value = df[column][j]
                if i == 0:
                    sql += ' '
                else:
                    sql += ' AND '
                if type(value) == str:
                    sql += column + ' = "' + value + '"'
                else:
                    sql += ' ABS(Subjects.' + column + ' - ' + str(value) + ') <= 0.01'
            sql += ' AND user_id = ' + str(self.user_id)
            try:
                found = self.cursor.execute(sql)
            except pms.err.InternalError as e:
                raise MetaDataError(e.args[1])
            if found >= 1:
                warnings.append('{}\t{}\tSubect in row {} already exists in the database.'.format(j + 2, subject_col, j + 2))
        return warnings

    def check_user_study_name(self, study_name):
        """ Checks if the current user has uploaded a study with the same name. """

        sql = 'SELECT * FROM Study WHERE user_id = {} and Study.StudyName = "{}"'
        found = self.cursor.execute(sql.format(self.user_id, study_name))
        ######### TEMPORARY ##########
        return []
        #########################
        if found >= 1:
            return ['-1\t-1\tUser {} has already uploaded a study with name {}'.format(self.owner, study_name)]
        else:
            return []

    def get_mongo_files(self, access_code):
        """ Return the three files necessary for qiime analysis. """
        mdata = MetaData.objects(access_code=access_code, owner=self.owner).first()

        # Raise an error if the upload does not exist
        if mdata is None:
            raise MissingUploadError('No data exist for this access code')

        mdata.last_accessed = datetime.utcnow()
        mdata.save()

        return mdata.files, mdata.path

    def get_metadata(self, access_code):
        """
        Return the MetaData object.
        This object should be treated as read only.
        Any modifications should be done through the Database class.
        """
        return MetaData.objects(access_code=access_code, owner=self.owner).first()

    def clean(self):
        """ Remove all temporary and intermediate files. """
        docs = MetaData.objects().first()
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
