import warnings

import mmeds.config as fig
import pandas as pd

from mmeds.error import NoResultError, InvalidSQLError
from mmeds.util import quote_sql, pyformat_translate
from mmeds.logging import Logger


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
            Table1_key ColA    ColB
            0          DataA   Datab

            Table2
            ------------------------------
            Table2_key   Table1_fkey   ColC   ColD
            2            0             DataC  DataD

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
        # For the SubjectType table one of the keys will be NULL depending on
        # if the metadata is for an Animal subject or a human subject
        if table == 'SubjectType':
            if self.df['SubjectType']['SubjectType'].iloc[self.row] == 'Human':
                del foreign_keys[foreign_keys.index('AnimalSubjects_idAnimalSubjects')]
            elif self.df['SubjectType']['SubjectType'].iloc[self.row] == 'Animal':
                del foreign_keys[foreign_keys.index('Subjects_idSubjects')]

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
            except TypeError:
                Logger.info('ACCEPTED TYPE ERROR FINDING FOREIGN KEYS')
                Logger.info(fsql)
                Logger.info(fargs)
                raise InvalidSQLError('No key found for SQL: {} with args: {}'.format(fsql, fargs))

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
