import importlib.util
import sys
import os
from socket import gethostname
import cherrypy as cp

# Not testing if running on Web01
testing = not (gethostname() == 'web01')

# Setup the path to mmeds (since it isn't being installed)
if testing:
    MODULE_PATH = "~/Work/mmeds-meta/mmeds/__init__.py"
    import mmeds
else:
    MODULE_PATH = "/hpc/users/mmedsadmin/www/mmeds-meta/mmeds/__init__.py"

    # import mmeds
    # Loading mmeds as a module without installation
    spec = importlib.util.spec_from_file_location("mmeds", MODULE_PATH)
    mmeds = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mmeds
    spec.loader.exec_module(mmeds)

# Imports
from mmeds.server import MMEDSserver
from mmeds.config import CONFIG
from mmeds.logging import Logger


curdir = os.path.abspath(os.path.dirname(__file__))


def application(environ, start_response):
    cp.config.update(mmeds.config.CONFIG)
    cp.server.unsubscribe()
    print('update please')
    print('hi again')

    print("hello there")
    if testing:
        web_path = '/myapp'
    else:
        web_path = '/mmeds_app/app.wsgi'
    app = cp.Application(MMEDSserver(), web_path, config=CONFIG)
    cp.tree.graft(app, web_path)
    return cp.tree(environ, start_response)
