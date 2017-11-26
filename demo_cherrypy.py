import random
import string
import os, os.path
import time
import cherrypy
import pymongog


DB_STRING = 'my.db'

class StringGenerator(object):

    @cherrypy.expose
    def index(self):
        return open('ajax.html')


@cherrypy.expose
class StringGeneratorWebService(object):

    @cherrypy.tools.accept(media='text/plain')
    def GET(self):
        with sqlite3.connect(DB_STRING) as c:
            cherrypy.session['ts'] = time.time()
            r = c.execute('SELECT value FROM user_string WHERE session_id=?',
                          [cherrypy.session.id])
        return r.fetchone()

    def POST(self, length=8):
        some_string = ''.join(random.sample(string.hexdigits, int(length)))
        with sqlite3.connect(DB_STRING) as c:
            cherrypy.session['ts'] = time.time()
            c.execute('INSERT INTO user_string VALUES (?, ?)',
                      [cherrypy.session.id, some_string])
        return some_string

    def PUT(self, another_string):
        with sqlite3.connect(DB_STRING) as c:
            cherrypy.session['ts'] = time.time()
            c.execute('UPDATE user_string SET value=? WHERE session_id=?',
                      [another_string, cherrypy.session.id])

    def DELETE(self):
        cherrypy.session.pop('mystring', None)
        with sqlite3.connect(DB_STRING) as c:
            c.execute('DELETE FROM user_string WHERE session_id=?',
                      [cherrypy.session.id])


def setup_database():
    with sqlite3.connect(DB_STRING) as con:
        con.execute("CREATE TABLE user_string (session_id, value)")


def cleanup_database():
    with sqlite3.connect(DB_STRING) as con:
        con.execute("DROP TABLE user_string")


if __name__ == '__main__':
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd())
        },
        '/generator': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'text/plain')]
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './public'
        }
    }

    cherrypy.engine.subscribe('start', setup_database)
    cherrypy.engine.subscribe('stop', cleanup_database)

    webapp = StringGenerator()
    webapp.generator = StringGeneratorWebService()

    cherrypy.quickstart(webapp, '/', conf)
