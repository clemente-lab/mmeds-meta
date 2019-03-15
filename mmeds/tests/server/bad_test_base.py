from mmeds.server import MMEDSbase

import mmeds.config as fig
from mmeds.authentication import add_user
from mmeds.error import LoggedOutError
from collections import defaultdict

import cherrypy as cp
from cherrypy.test import helper


class TestBase(helper.CPWebCase):

    global serv
    serv = MMEDSbase(True)

    def setup_server():
        cp.tree.mount(serv)
        test_config = defaultdict(dict)
        test_config['global']['tools.sessions.on'] = True
        test_config['global']['tools.sessions.name'] = 'cp_session'
        cp.config.update(test_config)

    setup_server = staticmethod(setup_server)
    add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL, True)

    def test_get_user(self):
        self.assertRaises(LoggedOutError, self.getPage('/get_user'))

    def test_get_dir(self):
        self.assertRaises(LoggedOutError, serv.get_dir())
