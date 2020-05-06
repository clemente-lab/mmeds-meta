import importlib.util
import sys
import os

# MODULE_PATH = "/hpc/users/wallad07/www/mmeds-meta/mmeds/__init__.py"
MODULE_PATH = "/home/david/Work/mmeds-meta/mmeds/__init__.py"
spec = importlib.util.spec_from_file_location("mmeds", MODULE_PATH)
mmeds = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mmeds
spec.loader.exec_module(mmeds)

from mmeds.server import MMEDSserver
from mmeds.config import CONFIG
from mmeds.spawn import Watcher
from multiprocessing.dummy import current_process, Queue, Pipe
from socket import gethostname
from mmeds.log import MMEDSLog

logger = MMEDSLog('wsgi-debug').logger

from sys import argv

import cherrypy as cp
curdir = os.path.abspath(os.path.dirname(__file__))


def secureheaders():
    headers = cp.response.headers
    headers['X-Frame-Options'] = 'DENY'
    headers['X-XSS-Protection'] = '1; mode=block'
    headers['Content-Security-Policy'] = 'default-src=self'
    if cp.server.ssl_certificate and cp.server.ssl_private_key:
        headers['Strict-Transport-Security'] = 'max-age=315360000'  # One Year


loaded = False

def application(environ, start_response):
    global loaded
    if not loaded:
        loaded = True
        logger.error('Loading')
        # Not testing if running on Web01
        testing = not (gethostname() == 'web01')
        # cp.tools.secureheaders = cp.Tool('before_finalize', secureheaders, priority=60)
        q = Queue()
        pipe_ends = Pipe()
        pipe = pipe_ends[0]
        watcher = mmeds.spawn.Watcher(q, pipe, current_process(), testing)
        watcher.start()
        cp.config.update(mmeds.config.CONFIG)
        cp.server.unsubscribe()

        web_path = '/~wallad07/mmeds-meta/alt_app.wsgi'
        web_path = '/myapp'
        app = cp.Application(mmeds.server.MMEDSserver(watcher, q, testing), web_path, config=mmeds.config.CONFIG)
        logger.error('Recreating application')
        cp.tree.graft(app, web_path)
    return cp.tree(environ, start_response)
