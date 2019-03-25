from mmeds.server import MMEDSserver
from time import sleep
from collections import defaultdict
from pathlib import Path
from tidylib import tidy_document

import mmeds.config as fig
import mmeds.error as err
from mmeds.authentication import add_user, remove_user
from mmeds.util import insert_error, insert_html, load_html, log, recieve_email, insert_warning

import cherrypy as cp
from cherrypy.test import helper


class TestServer(helper.CPWebCase):

    server_code = 'server_code_' + fig.get_salt(10)
    access_code = None

    def setup_server():
        cp.tree.mount(MMEDSserver(True))
        test_config = defaultdict(dict)
        test_config['global']['tools.sessions.on'] = True
        test_config['global']['tools.sessions.name'] = 'cp_session'
        cp.config.update(test_config)

    setup_server = staticmethod(setup_server)

    def test_a_setup(self):
        log('===== Test Server Start =====')

    def test_z_cleanup(self):
        remove_user(fig.SERVER_USER, testing=True)

    ############
    #  Stress  #
    ############

    def test_b_index(self):
        self.getPage('/index')
        self.assertStatus('200 OK')
        self.assertHeader('Content-Type', 'text/html;charset=utf-8')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    ####################
    #  Authentication  #
    ####################

    def not_logged_in(self):
        """ Check that trying to upload while not logged in takes you to the homepage """
        self.getPage('/index')
        self.assertStatus('200 OK')
        home_page = self.body
        self.getPage('/download/download_log')
        self.assertBody(home_page)
        self.getPage('/upload/upload_page')
        self.assertBody(home_page)

    def sign_up(self):
        addr = '/auth/sign_up?username={}&email={}&password1={}&password2={}'
        # Test signup with an invalid username
        self.getPage(addr.format('public', fig.TEST_EMAIL, fig.TEST_PASS, fig.TEST_PASS))
        self.assertStatus('200 OK')
        log('========================================')
        log(self.body)
        # Test signup with an invalid password
        self.getPage(addr.format(fig.SERVER_USER, fig.TEST_EMAIL, fig.TEST_PASS, fig.TEST_PASS + 'xx'))
        self.assertStatus('200 OK')
        log('========================================')
        log(self.body)
        # Test successful signup
        self.getPage(addr.format(fig.SERVER_USER, fig.TEST_EMAIL, fig.TEST_PASS, fig.TEST_PASS))
        self.assertStatus('200 OK')
        log('========================================')
        log(self.body)
        log('========================================')

    def login(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, fig.TEST_PASS))
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'welcome.html',
                         title='Welcome to Mmeds',
                         user=fig.SERVER_USER)
        self.assertBody(page)

    def logout(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, fig.TEST_PASS))
        self.getPage('/auth/logout', headers=self.cookies)
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    def login_fail_password(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, fig.TEST_PASS + 'garbage'))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 14, err.InvalidLoginError().message)
        self.assertBody(page)

    def login_fail_username(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER + 'garbage', fig.TEST_PASS))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 14, err.InvalidLoginError.message)
        self.assertBody(page)

    ############
    #  Access  #
    ############

    def upload_files(self, file_handles, file_paths, file_types):
        """ Helper method to setup headers and body for uploading a file """
        boundry = fig.get_salt(10)
        zipped = zip(file_handles, file_paths, file_types)
        b = b''
        for file_handle, file_path, file_type in zipped:
            # Byte strings
            b += str.encode('--{}\n'.format(boundry) +
                            'Content-Disposition: form-data; name="{}"; '.format(file_handle) +
                            'filename="{}"\r\n'.format(Path(file_path).name) +
                            'Content-Type: {}\r\n'.format(file_type) +
                            '\r\n')
            if not file_path == '':
                b += Path(file_path).read_bytes() + str.encode('\n')
            b + str.encode('\n')
        b += str.encode('--{}--\n'.format(boundry))

        filesize = len(b)
        h = [('Content-Type', 'multipart/form-data; boundary={}'.format(boundry)),
             ('Content-Length', str(filesize)),
             ('Connection', 'keep-alive')]
        return h, b

    def upload_metadata(self):
        # Check an invalid metadata filetype
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_GZ], ['application/gzip'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'upload_metadata_file.html', title='Upload Metadata', user=fig.SERVER_USER)
        err = 'Error: gz is not a valid filetype.'
        page = insert_error(page, 22, err)
        self.assertBody(page)

        # Check a metadata file that errors
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_METADATA_FAIL], ['text/tab-seperated-values'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page_body = self.body
        document, errors = tidy_document(page_body)
        # Assert no errors, warnings are okay
        for warn in errors:
            assert not ('error' in warn or 'Error' in warn)

        # Check a metadata file that produces warnings
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_METADATA_WARN], ['text/tab-seperated-values'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'upload_metadata_warning.html', title='Warnings', user=fig.SERVER_USER)
        warning = '34\t3\tStdDev Warning: Value 25.025 outside of two standard deviations of mean in column 3'
        page = insert_warning(page, 22, warning)
        self.assertBody(page)

        # Check a metadata file that has no issues
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_METADATA_SHORT], ['text/tab-seperated-values'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'upload_data_files.html', title='Upload Data', user=fig.SERVER_USER)
        self.assertBody(page)

    def upload_data(self):
        headers, body = self.upload_files(['for_reads', 'rev_reads', 'barcodes'],
                                          [fig.TEST_READS, '', fig.TEST_BARCODES],
                                          ['application/gzip', 'application/octet-stream', 'application/gzip'])
        self.getPage('/analysis/process_data', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        sleep(10)
        mail = recieve_email(1)
        code = mail[0].get_payload(decode=True).decode('utf-8')
        log(code)
        self.access_code = code.split('access code:')[1].splitlines()[1]

    def download_page_fail(self):
        self.getPage("/auth/login?username={}&password={}".format(fig.SERVER_USER, fig.TEST_PASS))
        self.getPage("/download/download_page?access_code={}".format(self.server_code + 'garbage'),
                     headers=self.cookies)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'welcome.html', title='Welcome to MMEDS', user=fig.SERVER_USER)
        page = insert_error(page, 22, err.MissingUploadError.message)
        self.assertBody(page)
        self.getPage('/auth/logout', headers=self.cookies)

    def download_block(self):
        # Login
        self.getPage("/auth/login?username={}&password={}".format(fig.SERVER_USER, fig.TEST_PASS))
        # Start test analysis
        self.getPage('/analysis/run_analysis?access_code={}&tool={}&config='.format(self.access_code,
                                                                                    fig.TEST_TOOL),
                     headers=self.cookies)
        sleep(2)
        # Try to access
        self.getPage("/download/download_page?access_code={}".format(self.access_code), headers=self.cookies)
        page = load_html(fig.HTML_DIR / 'welcome.html', user=fig.SERVER_USER, title='Welcome to MMEDS')
        page = insert_error(page, 22, 'Requested study is currently unavailable')
        self.assertBody(page)

        # Wait for analysis to finish
        sleep(int(fig.TEST_TOOL.split('-')[-1]))

        # Try to access again
        self.getPage("/download/download_page?access_code={}".format(self.access_code), headers=self.cookies)

        page = load_html(fig.HTML_DIR / 'download_select_file.html',
                         user=fig.SERVER_USER, title='Select Download')
        for i, f in enumerate(sorted(fig.TEST_FILES)):
            page = insert_html(page, 24 + i, '<option value="{}">{}</option>'.format(f, f))

        self.assertStatus('200 OK')
        self.assertBody(page)
        self.getPage('/logout', headers=self.cookies)

    def download(self):
        for download in fig.TEST_FILES:
            address = '/download/select_download?download={}'.format(download)
            self.getPage(address, headers=self.cookies)
            self.assertStatus('200 OK')

    def test_c_auth(self):
        self.not_logged_in()
        self.sign_up()
        self.login()
        self.logout()
        self.login_fail_password()
        self.login_fail_username()

    def test_d_upload(self):
        self.login()
        self.upload_metadata()
        self.upload_data()
        self.download_page_fail()
        self.download_block()
        self.download()
