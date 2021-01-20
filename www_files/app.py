import importlib.util
import sys
import os
from socket import gethostname
import cherrypy as cp

# Not testing if running on Web01
testing = not (gethostname() == 'web01')

# Setup the path to mmeds (since it isn't being installed)
if testing:
    MODULE_PATH = "/home/david/Work/mmeds-meta/mmeds/__init__.py"
    import mmeds
else:
    MODULE_PATH = "/hpc/users/wallad07/www/mmeds-meta/mmeds/__init__.py"

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


# Using a global to prevent the app from being generated multiple times
loaded = False


def create_app():
    cp.config.update(mmeds.config.CONFIG)
    cp.server.unsubscribe()

    if testing:
        web_path = '/myapp'
    else:
        web_path = '/mmeds_app/app.wsgi'
    app = cp.Application(MMEDSserver(), web_path, config=CONFIG)
    return app, web_path


def application(environ, start_response):
    global loaded
    if not loaded:
        loaded = True
        Logger.info("Reload this")
        app, web_path = create_app()
        cp.tree.graft(app, web_path)
    return cp.tree(environ, start_response)
