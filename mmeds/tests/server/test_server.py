from mmeds.server import MMEDSserver
from time import sleep
from collections import defaultdict
from pathlib import Path
from tidylib import tidy_document

import mmeds.config as fig
import mmeds.secrets as sec
import mmeds.error as err
from mmeds.authentication import remove_user
from mmeds.util import insert_error, insert_html, load_html, log, recieve_email, insert_warning

import cherrypy as cp
from cherrypy.test import helper


server = MMEDSserver(True)


class TestServer(helper.CPWebCase):

    server_code = 'server_code_' + fig.get_salt(10)
    access_code = None

    @staticmethod
    def setup_server():
        cp.tree.mount(server)
        test_config = defaultdict(dict)
        test_config['global']['tools.sessions.on'] = True
        test_config['global']['tools.sessions.name'] = 'cp_session'
        cp.config.update(test_config)

    def test_a_setup(self):
        log('===== Test Server Start =====')

    def test_b_index(self):
        self.getPage('/index')
        self.assertStatus('200 OK')
        self.assertHeader('Content-Type', 'text/html;charset=utf-8')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    def test_c_auth(self):
        self.not_logged_in()
        self.sign_up()
        self.login()
        self.logout()
        self.login_fail_password()
        self.login_fail_username()
        tp = self.reset_password()
        self.change_password(tp)

    def test_d_upload(self):
        return
        self.login()
        self.upload_metadata()
        self.upload_data()
        self.modify_upload()
        self.download_page_fail()
        self.download_block()
        self.download()
        self.convert()

    def test_z_cleanup(self):
        remove_user(fig.SERVER_USER, testing=True)

    ####################
    #  Authentication  #
    ####################

    def not_logged_in(self):
        """ Check that trying to upload while not logged in takes you to the homepage """
        self.getPage('/index')
        self.assertStatus('200 OK')
        home_page = self.body
        self.getPage('/analysis/query_page')
        self.assertBody(home_page)
        self.getPage('/upload/upload_page')
        self.assertBody(home_page)

    def sign_up(self):
        # Check the sign up input page
        self.getPage('/auth/sign_up_page')
        self.assertStatus('200 OK')

        page = (fig.HTML_DIR / 'auth_sign_up_page.html').read_text()
        addr = '/auth/sign_up?username={}&email={}&password1={}&password2={}'

        # Test signup with an invalid username
        faddr = addr.format('public', fig.TEST_EMAIL, sec.TEST_PASS, sec.TEST_PASS)
        self.getPage(faddr)
        self.assertStatus('200 OK')
        bad_page = insert_error(page, 25, 'Error: Username is invalid.')
        self.assertBody(bad_page)

        # Test signup with an invalid password
        self.getPage(addr.format(fig.SERVER_USER, fig.TEST_EMAIL, sec.TEST_PASS, sec.TEST_PASS + 'xx'))
        self.assertStatus('200 OK')
        bad_page = insert_error(page, 25, 'Error: Passwords do not match')
        self.assertBody(bad_page)

        # Test successful signup
        self.getPage(addr.format(fig.SERVER_USER, fig.TEST_EMAIL, sec.TEST_PASS, sec.TEST_PASS))
        self.assertStatus('200 OK')
        self.assertBody((fig.HTML_DIR / 'index.html').read_text())

    def login(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, sec.TEST_PASS))
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'welcome.html', title='Welcome to Mmeds', user=fig.SERVER_USER)
        self.assertBody(page)

    def logout(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, sec.TEST_PASS))
        self.getPage('/auth/logout', headers=self.cookies)
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    def login_fail_password(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, sec.TEST_PASS + 'garbage'))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 14, err.InvalidLoginError().message)
        self.assertBody(page)

    def login_fail_username(self):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER + 'garbage', sec.TEST_PASS))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 14, err.InvalidLoginError.message)
        self.assertBody(page)

    def change_password(self, new_pass):
        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, new_pass))
        self.assertStatus('200 OK')
        self.getPage('/auth/input_password', self.cookies)
        self.assertStatus('200 OK')
        temp_pass_bad = 'thi$1sT'
        self.getPage('/auth/change_password?password0={old}&password1={new}&password2={new}'.format(old=new_pass,
                                                                                                    new=temp_pass_bad),
                     self.cookies)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'auth_change_password.html', title='Change Password')
        fail_page = insert_error(page, 9, 'Error: Passwords must be longer than 10 characters.')
        self.assertBody(fail_page)
        self.getPage('/auth/change_password?password0={old}&password1={new}&password2={new}'.format(old=new_pass,
                                                                                                    new=sec.TEST_PASS),
                     self.cookies)
        self.assertStatus('200 OK')
        pass_page = insert_html(page, 9, 'Your password was successfully changed.')
        self.assertBody(pass_page)

        self.getPage('/auth/login?username={}&password={}'.format(fig.SERVER_USER, sec.TEST_PASS))
        self.assertStatus('200 OK')

    def reset_password(self):
        orig_page = (fig.HTML_DIR / 'index.html').read_text()
        self.getPage('/auth/password_recovery?username={}&email={}'.format(fig.SERVER_USER, fig.TEST_EMAIL + 'dfa'),
                     self.cookies)
        self.assertStatus('200 OK')
        fail_page = insert_error(orig_page, 14, 'No account exists with the provided username and email.')
        self.assertBody(fail_page)

        self.getPage('/auth/password_recovery?username={}&email={}'.format(fig.SERVER_USER, fig.TEST_EMAIL),
                     self.cookies)
        self.assertStatus('200 OK')
        pass_page = insert_html(orig_page, 14, 'A new password has been sent to your email.')
        self.assertBody(pass_page)

        sleep(20)
        mail = recieve_email(1)
        code = mail[0].get_payload(decode=True).decode('utf-8')
        new_pass = code.split('password is:')[1].splitlines()[1].strip()
        return new_pass

    def reset_access_code(self):
        return
        mail = recieve_email(1)
        code = mail[0].get_payload(decode=True).decode('utf-8')
        self.access_code = code.split('access code:')[1].splitlines()[1]
        pass

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
            b += str.encode('--{}\r\n'.format(boundry) +
                            'Content-Disposition: form-data; name="{}"; '.format(file_handle))
            if not file_type == '':
                b += str.encode('filename="{}"\r\n'.format(Path(file_path).name) +
                                'Content-Type: {}\r\n\r\n'.format(file_type))
                if not file_path == '':
                    b += Path(file_path).read_bytes() + str.encode('\r\n')
            else:
                b += str.encode('\r\n\r\n{}\r\n'.format(file_path))
            b + str.encode('\r\n')
        b += str.encode('--{}--\r\n'.format(boundry))

        filesize = len(b)
        h = [('Content-Type', 'multipart/form-data; boundary={}'.format(boundry)),
             ('Content-Length', str(filesize)),
             ('Connection', 'keep-alive')]
        return h, b

    def upload_metadata(self):
        # Check the page for uploading metadata
        self.getPage('/upload/upload_page', self.cookies)
        self.assertStatus('200 OK')
        self.getPage('/upload/upload_metadata?study_type=qiime', self.cookies)
        self.assertStatus('200 OK')
        # Check an invalid metadata filetype
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_GZ], ['application/gzip'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'upload_metadata_file.html', title='Upload Metadata', user=fig.SERVER_USER)
        err = 'Error: gz is not a valid filetype.'
        page = insert_error(page, 22, err)
        self.assertBody(page)
        log('Checked invalid filetype')

        # Check a metadata file that errors
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_METADATA_FAIL], ['text/tab-seperated-values'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page_body = self.body
        document, errors = tidy_document(page_body)
        # Assert no errors, warnings are okay
        for warn in errors:
            assert not ('error' in warn or 'Error' in warn)

        log('Checked metadata that errors')

        # Check a metadata file that produces warnings
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_METADATA_WARN], ['text/tab-seperated-values'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'upload_metadata_warning.html', title='Warnings', user=fig.SERVER_USER)
        warning = '31\t3\tStdDev Warning: Value 25.0 outside of two standard deviations of mean in column 3'
        page = insert_warning(page, 22, warning)
        self.assertBody(page)
        log('Checked metadata that warns')

        # Check a metadata file that has no issues
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_METADATA_SHORTEST], ['text/tab-seperated-values'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'upload_data_files.html', title='Upload Data', user=fig.SERVER_USER)
        self.assertBody(page)
        log('Checked a metadata file with no problems')

    def upload_data(self):
        self.getPage('/upload/upload_data', self.cookies)
        self.assertStatus('200 OK')
        headers, body = self.upload_files(['for_reads', 'rev_reads', 'barcodes', 'reads_type'],
                                          [fig.TEST_READS, '', fig.TEST_BARCODES, 'single_end'],
                                          ['application/gzip', 'application/octet-stream',
                                           'application/gzip', ''])
        log('TESTING INFO')
        log(headers)
        log(body)
        self.getPage('/analysis/process_data', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')

        sleep(20)
        mail = recieve_email(1)
        code = mail[0].get_payload(decode=True).decode('utf-8')
        self.access_code = code.split('access code:')[1].splitlines()[1]

    def modify_upload(self):
        headers, body = self.upload_files(['myData'], [fig.TEST_READS], ['application/gzip'])
        self.getPage('/upload/modify_upload?data_type=for_reads&access_code=badcode',
                     headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        orig_page = load_html(fig.HTML_DIR / 'upload_select_page.html', title='Upload Type', user=fig.SERVER_USER)
        err_page = insert_error(orig_page, 22, err.MissingUploadError().message)
        self.assertBody(err_page)
        self.getPage('/upload/modify_upload?data_type=for_reads&access_code={}'.format(self.access_code),
                     headers + self.cookies, 'POST', body)
        page = load_html(fig.HTML_DIR / 'welcome.html', title='Welcome to MMEDS', user=fig.SERVER_USER)
        page = insert_html(page, 22, 'Upload modification successful')
        self.assertStatus('200 OK')
        self.assertBody(page)

    def download_page_fail(self):
        self.getPage("/auth/login?username={}&password={}".format(fig.SERVER_USER, sec.TEST_PASS))
        self.getPage("/download/download_page?access_code={}".format(self.server_code + 'garbage'),
                     headers=self.cookies)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'welcome.html', title='Welcome to MMEDS', user=fig.SERVER_USER)
        page = insert_error(page, 22, err.MissingUploadError.message)
        self.assertBody(page)
        self.getPage('/auth/logout', headers=self.cookies)

    def download_block(self):
        # Login
        self.getPage("/auth/login?username={}&password={}".format(fig.SERVER_USER, sec.TEST_PASS))
        # Start test analysis
        self.getPage('/analysis/run_analysis?access_code={}&tool={}&config='.format(self.access_code,
                                                                                    fig.TEST_TOOL),
                     headers=self.cookies)
        sleep(20)
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

    def convert(self):
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_METADATA_SHORTEST], ['text/tab-seperated-values'])
        addr = '/upload/convert_metadata?convertTo=mixs&unitCol=&skipRows='
        self.getPage(addr, headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')

    ####################
    # Process Tracking #
    ####################
