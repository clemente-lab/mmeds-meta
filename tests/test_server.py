from server.server import MMEDSserver
from mmeds.config import TEST_CODE, TEST_CONFIG, HTML_DIR, TEST_USER, TEST_PASS, TEST_EMAIL
from mmeds.authentication import add_user
from mmeds.mmeds import insert_error
import cherrypy as cp
from cherrypy.test import helper


class TestServer(helper.CPWebCase):

    def setup_server():
        cp.tree.mount(MMEDSserver())
        cp.config.update(TEST_CONFIG)

    setup_server = staticmethod(setup_server)
    add_user(TEST_USER, TEST_PASS, TEST_EMAIL)

    ################################
    ###########  Stress  ###########
    ################################

    def test_index(self):
        self.getPage('/index')
        self.assertStatus('200 OK')
        self.assertHeader('Content-Type', 'text/html;charset=utf-8')
        with open(HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    ########################################
    ###########  Authentication  ###########
    ########################################

    def test_login(self):
        self.getPage('/login?username={}&password={}'.format(TEST_USER, TEST_PASS))
        self.assertStatus('200 OK')
        with open(HTML_DIR / 'welcome.html') as f:
            page = f.read().format(user=TEST_USER)
        self.assertBody(page)

    def test_logout(self):
        self.getPage('/login?username={}&password={}'.format(TEST_USER, TEST_PASS))
        self.getPage('/logout', headers=self.cookies)
        self.assertStatus('200 OK')
        with open(HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    def test_login_again(self):
        self.getPage('/login?username={}&password={}'.format(TEST_USER, TEST_PASS))
        self.assertStatus('200 OK')
        with open(HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 23, 'Error: User is already logged in.')
        self.assertBody(page)

    def test_login_fail(self):
        self.getPage('/login?username={}&password={}'.format(TEST_USER, TEST_PASS + 'garbage'))
        self.assertStatus('200 OK')
        with open(HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 23, 'Error: Invalid username or password.')
        self.assertBody(page)

    ###############################
    ###########  Access ###########
    ###############################

    def test_run_analysis(self):
        pass

    def test_download_page_fail(self):
        self.getPage("/login?username={}&password={}".format(TEST_USER, TEST_PASS))
        self.getPage("/download_page?access_code={}".format(TEST_CODE + 'garbage'), headers=self.cookies)
        self.assertStatus('200 OK')
        with open(HTML_DIR / 'download_error.html') as f:
            page = f.read().format(TEST_USER)
        self.assertBody(page)
        self.getPage('/logout', headers=self.cookies)
