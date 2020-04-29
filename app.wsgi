from mmeds.server import MMEDSserver
from mmeds.config import CONFIG
from mmeds.spawn import Watcher
from multiprocessing.dummy import current_process, Queue, Pipe
from socket import gethostname


from sys import argv
import cherrypy as cp


def secureheaders():
    headers = cp.response.headers
    headers['X-Frame-Options'] = 'DENY'
    headers['X-XSS-Protection'] = '1; mode=block'
    headers['Content-Security-Policy'] = 'default-src=self'
    if cp.server.ssl_certificate and cp.server.ssl_private_key:
        headers['Strict-Transport-Security'] = 'max-age=315360000'  # One Year


def application():
    # Not testing if running on Web01
    testing = not (gethostname() == 'web01')
    cp.tools.secureheaders = cp.Tool('before_finalize', secureheaders, priority=60)

    q = Queue()
    pipe_ends = Pipe()
    pipe = pipe_ends[0]
    watcher = Watcher(q, pipe, current_process(), testing)
    watcher.start()
    cp.config.update(CONFIG)
    return cp.Application(MMEDSserver(watcher, q, testing), '/', config=CONFIG)
