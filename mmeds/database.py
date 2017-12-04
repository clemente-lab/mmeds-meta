import pymysql as pms
import cherrypy as cp


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


def get_version(user, database):
    """ Returns the version of the database currently running. """
    db = pms.connect('localhost', 'root', '', 'MetaData')
    cursor = db.cursor()
    cursor.execute('SELECT VERSION()')
    data = cursor.fetchone()
    db.close()
    return ('Database version : %s' % data)
