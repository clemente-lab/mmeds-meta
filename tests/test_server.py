from server.server import MMEDSserver
from time import sleep

import mmeds.config as fig
from mmeds.authentication import add_user, remove_user
from mmeds.mmeds import insert_error, insert_html
from mmeds.database import Database

import cherrypy as cp
from cherrypy.test import helper


class TestServer(helper.CPWebCase):

    def setup_server():
        cp.tree.mount(MMEDSserver())
        cp.config.update(fig.TEST_CONFIG)

    setup_server = staticmethod(setup_server)
    add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL)
    with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER) as db:
        access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA,
                                                          'qiime',
                                                          reads=fig.TEST_READS,
                                                          barcodes=fig.TEST_BARCODES,
                                                          access_code=fig.TEST_CODE)

    ################################
    ###########  Stress  ###########
    ################################

    def test_index(self):
        self.getPage('/index')
        self.assertStatus('200 OK')
        self.assertHeader('Content-Type', 'text/html;charset=utf-8')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    ########################################
    ###########  Authentication  ###########
    ########################################

    def test_login(self):
        self.getPage('/login?username={}&password={}'.format(fig.TEST_USER, fig.TEST_PASS))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'welcome.html') as f:
            page = f.read().format(user=fig.TEST_USER)
        self.assertBody(page)

    def test_logout(self):
        self.getPage('/login?username={}&password={}'.format(fig.TEST_USER, fig.TEST_PASS))
        self.getPage('/logout', headers=self.cookies)
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    def test_login_again(self):
        self.getPage('/login?username={}&password={}'.format(fig.TEST_USER, fig.TEST_PASS))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 23, 'Error: User is already logged in.')
        self.assertBody(page)

    def test_login_fail(self):
        self.getPage('/login?username={}&password={}'.format(fig.TEST_USER, fig.TEST_PASS + 'garbage'))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 23, 'Error: Invalid username or password.')
        self.assertBody(page)

    ###############################
    ###########  Access ###########
    ###############################

    def test_run_analysis(self):
        pass

    def test_download_page_fail(self):
        self.getPage("/login?username={}&password={}".format(fig.TEST_USER, fig.TEST_PASS))
        self.getPage("/download_page?access_code={}".format(fig.TEST_CODE + 'garbage'), headers=self.cookies)
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'download_error.html') as f:
            page = f.read().format(fig.TEST_USER)
        self.assertBody(page)
        self.getPage('/logout', headers=self.cookies)

    def test_download_block(self):
        # Login
        self.getPage("/login?username={}&password={}".format(fig.TEST_USER, fig.TEST_PASS))
        # Start test analysis
        self.getPage('/run_analysis?access_code={}&tool={}'.format(fig.TEST_CODE, fig.TEST_TOOL), headers=self.cookies)
        # Try to access
        self.getPage("/download_page?access_code={}".format(fig.TEST_CODE), headers=self.cookies)
        with open(fig.HTML_DIR / 'welcome.html') as f:
            page = f.read().format(user=fig.TEST_USER)
        page = insert_error(page, 31, 'Requested study is currently unavailable')
        self.assertBody(page)

        # Wait for analysis to finish
        sleep(int(fig.TEST_TOOL.split('-')[-1]))
        del page

        # Try to access again
        self.getPage("/download_page?access_code={}".format(fig.TEST_CODE), headers=self.cookies)

        with open(fig.HTML_DIR / 'select_download.html') as f:
            page = f.read().format(fig.TEST_USER)
        for i, f in enumerate(fig.TEST_FILES):
            page = insert_html(page, 10 + i, '<option value="{}">{}</option>'.format(f, f))

        self.assertBody(page)
        self.getPage('/logout', headers=self.cookies)

    def test_download_page(self):
        self.getPage("/login?username={}&password={}".format(fig.TEST_USER, fig.TEST_PASS))
        self.getPage("/download_page?access_code={}".format(fig.TEST_CODE), headers=self.cookies)
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'select_download.html') as f:
            page = f.read().format(fig.TEST_USER)

        for i, f in enumerate(fig.TEST_FILES):
            page = insert_html(page, 10 + i, '<option value="{}">{}</option>'.format(f, f))

        self.assertBody(page)
        self.getPage('/logout', headers=self.cookies)

    def test_query(self):
        return
    """
        with Database(fig.TEST_DIR, user='mmeds_user', owner=TEST_USER) as db:
            status = db.set_mmeds_user(username)
            data, header = db.execute(query)
            html_data = db.format(data, header)
            with open(HTML_DIR / 'success.html', 'r') as f:
                page = f.read()
        pass
        """
