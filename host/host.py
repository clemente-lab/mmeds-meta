from mmeds.server import MMEDSserver
from mmeds.config import CONFIG
from mmeds.spawn import Watcher
from multiprocessing import current_process, Queue


from sys import argv
import cherrypy as cp


def secureheaders():
    headers = cp.response.headers
    headers['X-Frame-Options'] = 'DENY'
    headers['X-XSS-Protection'] = '1; mode=block'
    headers['Content-Security-Policy'] = 'default-src=self'
    if cp.server.ssl_certificate and cp.server.ssl_private_key:
        headers['Strict-Transport-Security'] = 'max-age=315360000'  # One Year


if __name__ == '__main__':
    try:
        testing = argv[1]
    except IndexError:
        testing = False
    cp.tools.secureheaders = cp.Tool('before_finalize', secureheaders, priority=60)

    q = Queue()
    watcher = Watcher(q, current_process(), testing)
    watcher.start()
    cp.quickstart(MMEDSserver(watcher, q, testing), config=CONFIG)
