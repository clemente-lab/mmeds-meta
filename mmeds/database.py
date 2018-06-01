import pymysql as pms
import mongoengine as men
import cherrypy as cp
import pandas as pd
import os

from prettytable import PrettyTable, ALL
from collections import defaultdict
from mmeds.config import SECURITY_TOKEN, TABLE_ORDER, get_salt


class MetaData(men.Document):
    study = men.StringField(max_length=45, required=True)
    access_code = men.StringField(max_length=50, required=True)
    owner = men.StringField(max_length=100, required=True)
    metadata = men.DictField()
    data = men.FileField()


class Database:

    def __init__(self, path, database='mmeds', user='root', owner=None):
        """
        Connect to the specified database.
        Initialize variables for this session.
        """
        try:
            if user == 'mmeds_user':
                self.db = pms.connect('localhost', user, 'password', database, local_infile=True)
            else:
                self.db = pms.connect('localhost', user, '', database, local_infile=True)
        except pms.err.ProgrammingError as e:
            cp.log('Error connecting to ' + database)
            raise e
        self.mongo = men.connect('test', host='127.0.0.1', port=27017)
        self.path = path
        self.IDs = defaultdict(dict)
        self.cursor = self.db.cursor()
        self.owner = owner
        if owner is None:
            self.user_id = 0
        else:
            sql = 'SELECT user_id FROM user WHERE user.username="' + owner + '"'
            self.cursor.execute(sql)
            self.user_id = int(self.cursor.fetchone()[0])

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
            if 'from' in sql:
                parsed = sql.split(' ')
                index = parsed.index('from')
                table = parsed[index + 1]
                self.cursor.execute('describe ' + table)
                header = [x[0] for x in self.cursor.fetchall()]
                return self.format(data, header)
            else:
                return self.format(data)
        except pms.err.ProgrammingError as e:
            cp.log('Error executing SQL command: ' + sql)
            cp.log(str(e))
            return str(e)

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
                if i == 0:
                    sql += ' '
                else:
                    sql += ' AND '
                if type(value) == str:
                    sql += column + ' = "' + value + '"'
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
        filename = os.path.join(self.path, table + '_input.csv')
        # Create the input file
        with open(filename, 'w') as f:
            f.write('\t'.join(columns) + '\n')
            # For each row in the input file
            for i in range(len(df.index)):
                line = []
                # For each column in the table
                for j, col in enumerate(columns):
                    # If the column is a primary key
                    if structure[j][3] == 'PRI':
                        key_table = col.split('id')[-1]
                        # Get the approriate data from the dictionary
                        try:
                            line.append(self.IDs[key_table][i])
                        except KeyError:
                            raise KeyError('Error getting key self.IDs[{}][{}]'.format(key_table, i))
                    elif structure[j][0] == 'user_id':
                        line.append(str(self.user_id))
                    elif structure[j][0] == 'AdditionalMetaDataRow':
                        line.append(str(i))
                    else:
                        # Otherwise see if the entry already exists
                        try:
                            line.append(df[table].loc[i][col])
                        except KeyError:
                            line.append(col)
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
                    f_key1 = self.IDs[columns[0]][key]
                    f_key2 = self.IDs[columns[1]][key]
                    key_pairs.append(str(f_key1) + '\t' + str(f_key2))

                # Remove any repeated pairs of foreign keys
                unique_pairs = list(set(key_pairs))
                filename = os.path.join(self.path, table + '_input.csv')

                # Create the input file for the juntion table
                with open(filename, 'w') as f:
                    f.write(columns[0] + '\t' + columns[1] + '\n')
                    for pair in unique_pairs:
                        f.write(pair + '\n')

                # Load the datafile in to the junction table
                sql = 'LOAD DATA LOCAL INFILE "' + filename + '" INTO TABLE ' +\
                      table + ' FIELDS TERMINATED BY "\\t"' +\
                      ' LINES TERMINATED BY "\\n" IGNORE 1 ROWS'
                self.cursor.execute(sql)
                # Commit the inserted data
                self.db.commit()
            except KeyError:
                pass

    def read_in_sheet(self, metadata, data, delimiter='\t'):
        """
        Creates table specific input csv files from the complete metadata file.
        Imports each of those files into the database.
        """
        access_code = None
        # Read in the metadata file to import
        df = pd.read_csv(metadata, sep=delimiter, header=[0, 1])
        df = df.reindex_axis(df.columns, axis=1)
        study_name = df['Study']['StudyName'][0]

        tables = df.axes[1].levels[0].tolist()
        tables.sort(key=lambda x: TABLE_ORDER.index(x))
        # Create file and import data for each regular table
        for table in tables:
            # Upload the additional meta data to the NoSQL database
            if table == 'AdditionalMetaData':
                access_code = self.mongo_import(df, data, study_name)
            else:
                self.create_import_data(table, df)
                filename = self.create_import_file(table, df)
                # Load the newly created file into the database
                sql = 'LOAD DATA LOCAL INFILE "' + filename + '" INTO TABLE ' +\
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

        return access_code, study_name

    def get_col_values_from_table(self, column, table):
        sql = 'SELECT {} FROM {}'.format(column, table)
        self.cursor.execute(sql)
        data = self.cursor.fetchall()
        return data

    def add_user(self, username, password, salt):
        """ Add the user with the specified parameters. """
        # Create the SQL to add the user
        sql = 'INSERT INTO mmeds.user (username, password, salt) VALUES\
                ("{}", "{}", "{}");'.format(username, password, salt)

        self.cursor.execute(sql)
        self.db.commit()

    def mongo_import(self, df, data, study_name, table='AdditionalMetaData'):
        """ Imports additional columns into the NoSQL database. """
        access_code = get_salt(50)
        # Convert dataframe to a dictionary
        new_mdata = df.to_dict('split')
        mdata = MetaData(study=study_name, access_code=access_code, owner=self.owner, metadata=new_mdata)
        if data is not None:
            # Open the data file
            with open(data, 'rb') as data_file:
                # Add a document for the study in the NoSQL
                mdata.data.put(data_file)
        # Save the document
        mdata.save()
        return access_code

    def get_data_from_access_code(self, access_code):
        """ Gets the NoSQL data affiliated with the provided access code. """
        mdata = MetaData.objects(access_code=access_code, owner=self.owner).first()
        return mdata.data

    def modify_data(self, new_data, access_code):
        mdata = MetaData.objects(access_code=access_code, owner=self.owner).first()
        # Open the data file
        with open(new_data, 'rb') as data_file:
            mdata.data.replace(data_file)
            mdata.save()
