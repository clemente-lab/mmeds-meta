from mmeds.config import CONFIG, STORAGE_DIR
import mmeds.secrets as sec
from app import application

# Import CherryPy
import cherrypy

if __name__ == '__main__':

    # Mount the application
    cherrypy.tree.graft(application, "/")

    # Unsubscribe the default server
    cherrypy.server.unsubscribe()
    #cherrypy.config.update(CONFIG)

    # Instantiate a new server object
    server = cherrypy._cpserver.Server()

    server.socket_host = sec.SERVER_HOST
    server.socket_port = sec.SERVER_PORT
    server.socket_timeout = 1000000000
    server.max_request_body_size = 10000000000
    server.ssl_module = 'builtin'
    server.ssl_certificate = str(STORAGE_DIR / 'cert.pem')
    server.ssl_private_key = str(STORAGE_DIR / 'key.pem')

    # Subscribe this server
    server.subscribe()


    # Start the server engine (Option 1 *and* 2)

    cherrypy.config.update(CONFIG)
    cherrypy.engine.start()
    cherrypy.engine.block()
