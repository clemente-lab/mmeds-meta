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


def list_tables():
    """ Logs the availible tables in the database. """
    db = pms.connect('localhost', 'root', '', 'MetaData')
    cursor = db.cursor()

    sql = 'SELECT owner, table_name FROM all_tables'
    cursor.execute(sql)

    data = cursor.fetchone()
    cp.log(data)
    db.close()


def get_version(user, database):
    """ Returns the version of the database currently running. """
    db = pms.connect('localhost', 'root', '', 'MetaData')
    cursor = db.cursor()
    cursor.execute('SELECT VERSION()')
    data = cursor.fetchone()
    db.close()
    return ('Database version : %s' % data)
