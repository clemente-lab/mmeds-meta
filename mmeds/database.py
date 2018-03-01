import pymysql as pms
import cherrypy as cp
import pandas as pd
import os

from collections import defaultdict


def insert(table, pi, lab):
    """ Inserts ITEM into TABLE of database. """
    db = pms.connect('localhost', 'root', '', 'MetaData')
    cursor = db.cursor()

    sql = 'INSERT INTO %s(PRIMARY_INVESTIGATOR, LAB) VALUES ("%s", "%s")' % (table, pi, lab)

    try:
        cursor.execute(sql)
        db.commit()
    except pms.err.ProgrammingError:
        cp.log('Error inserting into database')
        db.rollback()
    db.close()


def list_tables(database, user='root'):
    """ Logs the availible tables in the database. """
    db = pms.connect('localhost', user, '', database)
    cp.log('Connected to database ' + database + ' as user ' + user)
    cursor = db.cursor()
    cp.log('Got cursor from database')
    try:
        sql = 'SHOW TABLES;'
        cursor.execute(sql)
        cp.log('Ran query')
        data = cursor.fetchall()
        cp.log('\n'.join(map(str, data)))
    except pms.err.ProgrammingError as e:
        cp.log('Error executing SQL command: ' + sql)
        cp.log(str(e))
    db.close()


def connect(database='mmeds_db', user='root'):
    """ Connect to the specified database. """
    try:
        db = pms.connect('localhost', user, '', database)
        cp.log('Successfully connected to ' + database)
    except pms.err.ProgrammingError:
        cp.log('Error connecting to ' + database)
    return db


def disconnect(db):
    """ Connect to the specified database. """
    try:
        db.close()
        cp.log('Disconnected from database.')
    except pms.err.ProgrammingError:
        cp.log('Error closing connection to database.')


def execute(db, sql):
    """ Execute the provided sql script using the provided database cursor. """
    try:
        cursor = db.cursor()
        cursor.execute(sql)
        data = cursor.fetchall()
        cp.log('\n'.join(map(str, data)))
    except pms.err.ProgrammingError as e:
        cp.log('Error executing SQL command: ' + sql)
        cp.log(str(e))


def get_version(user='root', database='mmeds_db'):
    """ Returns the version of the database currently running. """
    db = pms.connect('localhost', user, '', database)
    cursor = db.cursor()
    cursor.execute('SELECT VERSION()')
    data = cursor.fetchone()
    db.close()
    return ('Database version : %s' % data)


def read_in_sheet(fp, delimiter='\t', path='/home/david/Work/mmeds-meta/test_files/'):
    db = connect()
    df = pd.read_csv(fp, delimiter=delimiter, header=[0, 1])
    cursor = db.cursor()
    current_key = 0
    IDs = defaultdict(dict)
    # Go through each table
    for table in df.axes[1].levels[0]:
        sql = 'SELECT COUNT(*) FROM ' + table
        cursor.execute(sql)
        current_key = int(cursor.fetchone()[0])
        # Track keys for repeated values in this file
        seen = {}
        # Go through each column
        for j in range(len(df.index)):
            sql = 'SELECT * FROM ' + table + ' WHERE'
            for i, column in enumerate(df[table]):
                if i == 0:
                    sql += ' ' + column + ' = "' + str(df[table][column][j] + '"')
                else:
                    sql += ' AND ' + column + ' = "' + str(df[table][column][j] + '"')
            # Check if there is a matching entry in the table
            found = cursor.execute(sql)
            # print('Return : %d' % found)
            if found == 1:
                result = cursor.fetchone()
                # Append the key found for that column
                IDs[table][j] = int(result[0])
            else:
                this_row = ''.join(df[table].loc[j])
                try:
                    key = seen[this_row]
                    IDs[table][j] = key
                except KeyError:
                    seen[this_row] = current_key
                    IDs[table][j] = current_key
                    current_key += 1

        sql = 'DESCRIBE ' + table
        cursor.execute(sql)
        structure = cursor.fetchall()
        columns = list(map(lambda x: x[0], structure))
        print(columns)
        with open(os.path.join(path, table + '_input.csv'), 'w') as f:
            f.write('\t'.join(columns) + '\n')
            for i in range(len(df.index)):
                for j, col in enumerate(columns):
                    try:
                        print(df[table].loc[i][col])
                    except KeyError:
                        print(col)
                    pass


    for table in IDs.keys():
        for column in IDs[table].keys():
            print('IDs[%s][%s]: %d' % (table, column, IDs[table][column]))
    disconnect(db)
    return df
