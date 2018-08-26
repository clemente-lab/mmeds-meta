from server.server import MMEDSserver
from mmeds.config import TEST_CONFIG, HTML_DIR, TEST_USER, TEST_PASS, TEST_EMAIL
from mmeds.authentication import add_user
import cherrypy as cp
from cherrypy.test import helper


class SimpleCPTest(helper.CPWebCase):

    def setup_server():
        cp.tree.mount(MMEDSserver())
        cp.config.update(TEST_CONFIG)

    setup_server = staticmethod(setup_server)
    add_user(TEST_USER, TEST_PASS, TEST_EMAIL)

    def test_index(self):
        self.getPage("/index")
        self.assertStatus('200 OK')
        self.assertHeader('Content-Type', 'text/html;charset=utf-8')
        with open(HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    def test_login(self):
        self.getPage("/login?username={}&password={}".format(TEST_USER, TEST_PASS))
        self.assertStatus('200 OK')
