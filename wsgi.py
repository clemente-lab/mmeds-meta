# Import your application as:
# from wsgi import application
# Example:

from mmeds.config import CONFIG, STORAGE_DIR
import mmeds.secrets as sec
from app import application

# Import CherryPy
import cherrypy

if __name__ == '__main__':

    # Mount the application
    cherrypy.tree.graft(application(), "/")

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

    # For SSL Support
    # server.ssl_module            = 'pyopenssl'
    # server.ssl_certificate       = 'ssl/certificate.crt'
    # server.ssl_private_key       = 'ssl/private.key'
    # server.ssl_certificate_chain = 'ssl/bundle.crt'

    # Subscribe this server
    server.subscribe()

    # Example for a 2nd server (same steps as above):
    # Remember to use a different port

    # server2             = cherrypy._cpserver.Server()

    # server2.socket_host = "0.0.0.0"
    # server2.socket_port = 8081
    # server2.thread_pool = 30
    # server2.subscribe()

    # Start the server engine (Option 1 *and* 2)

    cherrypy.config.update(CONFIG)
    cherrypy.engine.start()
    cherrypy.engine.block()
