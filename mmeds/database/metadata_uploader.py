import warnings

import mmeds.secrets as sec
import mmeds.config as fig
import mongoengine as men
import pymysql as pms
import pandas as pd

from datetime import datetime
from pathlib import WindowsPath, Path
from collections import defaultdict
from multiprocessing import Process
from mmeds.error import NoResultError
from mmeds.util import (quote_sql, parse_ICD_codes, send_email, create_local_copy,
                        load_metadata, join_metadata, write_metadata)
from mmeds.database.sql_builder import SQLBuilder
from mmeds.database.documents import MMEDSDoc
from mmeds.logging import Logger


class MetaDataUploader(Process):
    """
    This class handles the yprocessing and uploading of mmeds metadata files into the MySQL database.
    """
    def __init__(self, subject_metadata, subject_type, specimen_metadata, owner, study_type,
                 study_name, meta_study, temporary, public, testing, access_code=None):
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
        super().__init__()
        Logger.debug('MetadataUploader created with params')
        Logger.debug({
            'subject_metadata': subject_metadata,
            'specimen_metadata': specimen_metadata,
            'owner': owner,
            'study_type': study_type,
            'study_name': study_name,
            'meta_study': meta_study,
            'temporary': temporary,
            'public': public,
            'testing': testing
        })

        self.subject_type = subject_type
        self.IDs = defaultdict(dict)
        self.owner = owner
        self.testing = testing
        self.study_type = study_type
        self.subject_metadata = Path(subject_metadata)
        self.specimen_metadata = Path(specimen_metadata)
        self.study_name = study_name
        self.meta_study = meta_study
        self.temporary = temporary
        self.public = public
        self.created = datetime.now()

        # Like Database, this should be replaced with a switch statement
        # If testing connect to test server
        if testing:
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

        if access_code is None:
            self.access_code = fig.get_salt(50)
            # Ensure a unique access code
            while list(MMEDSDoc.objects(access_code=self.access_code)):
                self.access_code = fig.get_salt(50)
        else:
            self.access_code = access_code

        # Create the document
        self.mdata = MMEDSDoc(created=datetime.utcnow(),
                              last_accessed=datetime.utcnow(),
                              testing=self.testing,
                              doc_type='study',
                              tool_type=self.study_type,
                              study_name=self.study_name,
                              access_code=self.access_code,
                              owner=self.owner,
                              public=self.public)

        self.mdata.save()

        count = 0
        new_dir = fig.STUDIES_DIR / ('{}_{}_{}'.format(self.owner, self.study_name, count))
        while new_dir.is_dir():
            count += 1
            new_dir = fig.STUDIES_DIR / ('{}_{}_{}'.format(self.owner, self.study_name, count))
        new_dir.mkdir()

        self.path = Path(new_dir) / 'database_files'
        MMEDSDoc.objects.timeout(False)

    def get_info(self):
        """ Method to return a dictionary of relevant info for the process log """
        info = {
            'created': self.created,
            'type': 'upload',
            'owner': self.owner,
            'study_code': self.access_code,
            'pid': self.pid,
            'name': self.name,
            'exitcode': self.exitcode
        }
        return info

    def run(self):
        """
        Thread that handles the upload of large data files.
        ===================================================
        :metadata_copy: A string. Location of the metadata.
        :reads: A tuple. First element is the name of the reads/data file,
                         the second is a file type io object
        :barcodes: A tuple. First element is the name of the barcodes file,
                            the second is a file type io object
        :testing: True if the server is running locally.
        :datafiles: A list of datafiles to be uploaded
        """
        self.mdata.update(is_alive=True)
        self.mdata.save()
        Logger.debug('Handling upload for study {} for user {}'.format(self.study_name, self.owner))

        # Create a copy of the MetaData
        with open(self.subject_metadata, 'rb') as f:
            subject_metadata_copy = create_local_copy(f, self.subject_metadata.name, self.path.parent)

        # Create a copy of the Specimen MetaData
        with open(self.specimen_metadata, 'rb') as f:
            specimen_metadata_copy = create_local_copy(f, self.specimen_metadata.name, self.path.parent)

        # Merge the metadata files
        metadata_copy = str(Path(subject_metadata_copy).parent / 'full_metadata.tsv')
        metadata_df = join_metadata(load_metadata(subject_metadata_copy),
                                    load_metadata(specimen_metadata_copy),
                                    self.subject_type)
        self.metadata = metadata_copy
        write_metadata(metadata_df, metadata_copy)

        if not self.temporary:
            # Read in the metadata file to import
            if self.subject_type == 'human' or self.subject_type == 'mixed':
                df = parse_ICD_codes(load_metadata(metadata_copy))
            elif self.subject_type == 'animal':
                df = load_metadata(metadata_copy)
            self.df = df.reindex(df.columns, axis=1)
            self.builder = SQLBuilder(self.df, self.db, self.owner)

        # If the owner is None set user_id to 0
        if self.owner is None:
            self.user_id = 0
            self.email = fig.MMEDS_EMAIL
        # Otherwise get the user id for the owner from the database
        else:
            sql = 'SELECT user_id, email FROM user WHERE user.username=%(uname)s'
            cursor = self.db.cursor()
            cursor.execute(sql, {'uname': self.owner})
            result = cursor.fetchone()
            cursor.close()
            # Ensure the user exists
            if result is None:
                raise NoResultError('No account exists with the provided username and email.')
            self.user_id = int(result[0])
            self.email = result[1]

        # If the metadata is to be made public overwrite the user_id
        if self.public:
            self.user_id = 1
        self.check_file = fig.DATABASE_DIR / 'last_check.dat'

        # Save files to document
        self.import_metadata()
        # Send the confirmation email
        send_email(self.email, self.owner, message='upload', study=self.study_name,
                   code=self.access_code, testing=self.testing)

        # Update the doc to reflect the successful upload
        self.mdata.update(is_alive=False, exit_code=0)
        self.mdata.save()
        return 0

    def import_metadata(self, **kwargs):
        """
        Creates table specific input csv files from the complete metadata file.
        Imports each of those files into the database.
        """

        if not self.path.is_dir():
            self.path.mkdir()

        # Import the files into the mongo database
        self.mongo_import(**kwargs)

        # If the metadata file is not temporary perform the import into the SQL database
        # If study is meta study also do not perform import, all data is already there
        if not self.temporary and not self.meta_study:
            # Sort the available tables based on TABLE_ORDER
            columns = self.df.columns.levels[0].tolist()
            column_order = [fig.TABLE_ORDER.index(col) for col in columns]
            tables = [x for _, x in sorted(zip(column_order, columns)) if not x == 'ICDCode']

            # Disable the table Weight Triggers
            with self.db.cursor() as cursor:
                cursor.execute('SET @DISABLE_TRIGGERS = TRUE')
            self.db.commit()

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
                    with self.db.cursor() as cursor:
                        cursor.execute(sql, {'file': str(filename), 'table': table})
                    # Commit the inserted data
                    self.db.commit()

            # Create csv files and import them for
            # each junction table
            self.fill_junction_tables()

            # Remove all row information from the current input
            self.IDs.clear()

            # Reenable the table Weight Triggers
            with self.db.cursor() as cursor:
                cursor.execute('SET @DISABLE_TRIGGERS = FALSE')
            self.db.commit()

    def create_import_data(self, table, verbose=True):
        """
        Fill out the dictionaries used to create the input files from the input data file.
        =================================================================================
        :table: The table in the database to create the import data for
        :verbose: Doesn't do anything currently. Intended to be a logging flag
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
            Logger.info(sql)
            Logger.info(args)
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
        :structure: The structure of the SQL table the line will be imported into
        :columns: A list. The columns of the table to fill out
        :row_index: A int. The index of the row of the metadata this line corresponds to
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
                    # Depending on the type of the subject one of these keys should be NULL
                    # Check for that case before raising an Error
                    if ((key_table == 'AnimalSubjects' and
                         self.df['SubjectType']['SubjectType'].iloc[row_index] == 'Human') or
                        (key_table == 'Subjects' and
                         not self.df['SubjectType']['SubjectType'].iloc[row_index] == 'Human')):
                        line.append('\\N')
                    else:
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
        Create the file to load into each table referenced in the metadata input file
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
                with self.db.cursor() as cursor:
                    cursor.execute(sql, {'file': str(filename), 'table': table})
                # Commit the inserted data
                self.db.commit()
            except KeyError as e:
                e.args[1] += '\t{}\n'.format(str(filename))
                raise e

    def mongo_import(self, **kwargs):
        """ Imports additional columns into the NoSQL database. """
        # Add the files approprate to the type of study
        self.mdata.files.update(kwargs)
        self.mdata.files['metadata'] = self.metadata
        self.mdata.update(email=self.email, path=str(self.path.parent))
        # Save the document
        self.mdata.save()
