from mmeds.server import MMEDSserver
from time import sleep
from collections import defaultdict

import mmeds.config as fig
import mmeds.error as err
from mmeds.authentication import add_user
from mmeds.util import insert_error, insert_html, load_html
from mmeds.database import Database

import cherrypy as cp
from cherrypy.test import helper


class TestServer(helper.CPWebCase):

    def setup_server():
        cp.tree.mount(MMEDSserver(True))
        test_config = defaultdict(dict)
        test_config['global']['tools.sessions.on'] = True
        test_config['global']['tools.sessions.name'] = 'cp_session'
        cp.config.update(test_config)

    setup_server = staticmethod(setup_server)
    add_user(fig.SERVER_USER, fig.TEST_PASS, fig.TEST_EMAIL, True)
    with Database(fig.TEST_DIR, user='root', owner=fig.SERVER_USER, testing=True) as db:
        access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA,
                                                          'qiime',
                                                          reads=fig.TEST_READS,
                                                          barcodes=fig.TEST_BARCODES,
                                                          access_code=fig.TEST_CODE,
                                                          testing=True)

    ############
    #  Stress  #
    ############

    def test_index(self):
        self.getPage('/index')
        self.assertStatus('200 OK')
        self.assertHeader('Content-Type', 'text/html;charset=utf-8')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    ####################
    #  Authentication  #
    ####################

    def test_login(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, fig.TEST_PASS))
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'welcome.html',
                         title='Welcome to Mmeds',
                         user=fig.SERVER_USER)
        self.assertBody(page)

    def test_logout(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, fig.TEST_PASS))
        self.getPage('/auth/logout', headers=self.cookies)
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    def test_login_fail_password(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, fig.TEST_PASS + 'garbage'))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 14, err.InvalidLoginError().message)
        self.assertBody(page)

    def test_login_fail_username(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER + 'garbage', fig.TEST_PASS))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 14, err.InvalidLoginError.message)
        self.assertBody(page)

    ############
    #  Access  #
    ############

    def test_download_page_fail(self):
        self.getPage("/auth/login?username={}&password={}".format(fig.SERVER_USER, fig.TEST_PASS))
        self.getPage("/download/download_page?access_code={}".format(fig.TEST_CODE + 'garbage'), headers=self.cookies)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'welcome.html', title='Welcome to MMEDS', user=fig.SERVER_USER)
        page = insert_error(page, 22, err.MissingUploadError.message)
        self.assertBody(page)
        self.getPage('/auth/logout', headers=self.cookies)

    """
    def test_download_block(self):
        # Login
        self.getPage("/auth/login?username={}&password={}".format(fig.SERVER_USER, fig.TEST_PASS))
        # Start test analysis
        self.getPage('/analysis/run_analysis?access_code={}&tool={}&config='.format(fig.TEST_CODE,
                                                                                    fig.TEST_TOOL),
                     headers=self.cookies)
        # Try to access
        self.getPage("/download/download_page?access_code={}".format(fig.TEST_CODE), headers=self.cookies)
        page = load_html(fig.HTML_DIR / 'welcome.html', user=fig.SERVER_USER, title='Welcome to MMEDS')
        page = insert_error(page, 31, 'Requested study is currently unavailable')
        self.assertBody(page)

        # Wait for analysis to finish
        sleep(int(fig.TEST_TOOL.split('-')[-1]))
        del page

        # Try to access again
        self.getPage("/download/download_page?access_code={}".format(fig.TEST_CODE), headers=self.cookies)

        page = load_html(fig.HTML_DIR / 'download_select_file.html',
        user=fig.SERVER_USER, title='MMEDS Analysis Server')
        for i, f in enumerate(fig.TEST_FILES):
            page = insert_html(page, 10 + i, '<option value="{}">{}</option>'.format(f, f))

        self.assertBody(page)
        self.getPage('/logout', headers=self.cookies)

    def test_download_page(self):
        return
        self.getPage("/auth/login?username={}&password={}".format(fig.SERVER_USER, fig.TEST_PASS))
        self.getPage("/download/download_page?access_code={}".format(fig.TEST_CODE), headers=self.cookies)
        with open(fig.HTML_DIR / 'select_download.html') as f:
            page = f.read().format(fig.SERVER_USER)

        for i, f in enumerate(fig.TEST_FILES):
            page = insert_html(page, 10 + i, '<option value="{}">{}</option>'.format(f, f))

        self.assertBody(page)
        self.getPage('/logout', headers=self.cookies)

    def test_download(self):
        return
        downloads = [
            'barcodes',
            'reads',
            'metadata'
        ]
        for download in downloads:
            address = '/download/select_download?download={}'.format(download)
            self.getPage(address)
            print(self.body)

    def test_query(self):
        return

    """