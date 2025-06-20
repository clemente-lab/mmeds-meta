import subprocess
import importlib.util
import sys
import os
from socket import gethostname
import cherrypy as cp

sys.path.append("/sc/arion/projects/MMEDS/.modules/mmeds_test/lib/python3.9/site-packages")
import pandas as pd

# Not testing if running on Web03
testing = not ('web03' in gethostname())

# Setup the path to mmeds (since it isn't being installed)
if testing:
    MODULE_PATH = "~/Work/mmeds-meta/mmeds/__init__.py"
    import mmeds
else:
    # MODULE_PATH = "/hpc/users/mmedsadmin/www/mmeds-meta/mmeds/__init__.py"
    MODULE_PATH = "/sc/arion/projects/MMEDS/.modules/mmeds_test/lib/python3.9/site-packages/mmeds/__init__.py"
    # import mmeds
    # Loading mmeds as a module without installation
    spec = importlib.util.spec_from_file_location("mmeds", MODULE_PATH)
    mmeds = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mmeds
    spec.loader.exec_module(mmeds)

    MULTIPROCESSING_PATH = "/sc/arion/projects/MMEDS/.modules/mmeds_test/lib/python3.9/multiprocessing/__init__.py"
    # import mmeds
    # Loading mmeds as a module without installation
    spec = importlib.util.spec_from_file_location("multiprocessing", MULTIPROCESSING_PATH)
    multiprocessing = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = multiprocessing
    spec.loader.exec_module(multiprocessing)

# Imports
from mmeds.server import MMEDSserver
from mmeds.config import CONFIG
from mmeds.logging import Logger

import multiprocessing
import multiprocessing.managers

curdir = os.path.abspath(os.path.dirname(__file__))


def application(environ, start_response):
    cp.config.update(mmeds.config.CONFIG)
    cp.server.unsubscribe()

    if testing:
        web_path = '/myapp'
    else:
        web_path = '/mmeds_app/app.wsgi'
    app = cp.Application(MMEDSserver(), web_path, config=CONFIG)
    cp.tree.graft(app, web_path)
    return cp.tree(environ, start_response)
