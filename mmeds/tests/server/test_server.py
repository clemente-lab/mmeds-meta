from mmeds.server import MMEDSserver
from time import sleep, time
from collections import defaultdict
from pathlib import Path
from tidylib import tidy_document

import mmeds.config as fig
import mmeds.secrets as sec
import mmeds.error as err
from mmeds.authentication import add_user, remove_user
from mmeds.util import insert_error, insert_html, load_html, log, recieve_email, insert_warning

import cherrypy as cp
from cherrypy.test import helper


server = MMEDSserver(True)


class TestServer(helper.CPWebCase):

    server_code = 'server_code_' + fig.get_salt(10)
    # Create a unique user id from the current time
    server_user = fig.SERVER_USER + str(int(time()))
    access_code = None
    lab_user = 'lab_user_' + fig.get_salt(10)
    testing = True

    @staticmethod
    def setup_server():
        cp.tree.mount(server)
        test_config = defaultdict(dict)
        test_config['global']['tools.sessions.on'] = True
        test_config['global']['tools.sessions.name'] = 'cp_session'
        cp.config.update(test_config)

    def test_a_setup(self):
        log('===== Test Server Start =====')
        add_user(self.lab_user, sec.TEST_PASS, fig.TEST_EMAIL, 1, True)

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
        self.login()
        self.upload_metadata()
        self.upload_data()
        self.modify_upload()
        self.download_page_fail()
        self.download_block()
        self.download()
        self.convert()
        self.lab_download()

    def test_z_cleanup(self):
        remove_user(self.server_user, testing=self.testing)
        remove_user(self.lab_user, testing=self.testing)

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
        self.getPage(addr.format(self.server_user, fig.TEST_EMAIL, sec.TEST_PASS, sec.TEST_PASS + 'xx'))
        self.assertStatus('200 OK')
        bad_page = insert_error(page, 25, 'Error: Passwords do not match')
        self.assertBody(bad_page)

        # Test successful signup
        self.getPage(addr.format(self.server_user, fig.TEST_EMAIL, sec.TEST_PASS, sec.TEST_PASS))
        self.assertStatus('200 OK')
        self.assertBody((fig.HTML_DIR / 'index.html').read_text())

    def login(self):
        self.getPage('/auth/login?username={}&password={}'.format(self.server_user, sec.TEST_PASS))
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'welcome.html', title='Welcome to Mmeds', user=self.server_user)
        self.assertBody(page)

    def logout(self):
        self.getPage('/auth/login?username={}&password={}'.format(self.server_user, sec.TEST_PASS))
        self.getPage('/auth/logout', headers=self.cookies)
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        self.assertBody(page)

    def login_fail_password(self):
        self.getPage('/auth/login?username={}&password={}'.format(self.server_user, sec.TEST_PASS + 'garbage'))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 14, err.InvalidLoginError().message)
        self.assertBody(page)

    def login_fail_username(self):
        self.getPage('/auth/login?username={}&password={}'.format(self.server_user + 'garbage', sec.TEST_PASS))
        self.assertStatus('200 OK')
        with open(fig.HTML_DIR / 'index.html') as f:
            page = f.read()
        page = insert_error(page, 14, err.InvalidLoginError.message)
        self.assertBody(page)

    def change_password(self, new_pass):
        self.getPage('/auth/login?username={}&password={}'.format(self.server_user, new_pass))
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

        self.getPage('/auth/login?username={}&password={}'.format(self.server_user, sec.TEST_PASS))
        self.assertStatus('200 OK')

    def reset_password(self):
        orig_page = (fig.HTML_DIR / 'index.html').read_text()
        self.getPage('/auth/password_recovery?username={}&email={}'.format(self.server_user, fig.TEST_EMAIL + 'dfa'),
                     self.cookies)
        self.assertStatus('200 OK')
        fail_page = insert_error(orig_page, 14, 'No account exists with the provided username and email.')
        self.assertBody(fail_page)

        self.getPage('/auth/password_recovery?username={}&email={}'.format(self.server_user, fig.TEST_EMAIL),
                     self.cookies)
        self.assertStatus('200 OK')
        pass_page = insert_html(orig_page, 14, 'A new password has been sent to your email.')
        self.assertBody(pass_page)

        # Arguments for finding the right email
        password_args = [
            ['FROM', fig.MMEDS_EMAIL],
            ['TEXT', 'Hello {},'.format(self.server_user)],
            ['TEXT', 'Your password has been reset.']
        ]
        mail = recieve_email(1, True, password_args)
        code = mail[0].get_payload(decode=True).decode('utf-8')
        new_pass = code.split('password is:')[1].splitlines()[1].strip()
        return new_pass

    def reset_access_code(self):
        return
        mail = recieve_email(1, True, self.email_args)
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
            # IF the file_type is '' treat it as a string param
            if file_type == '':
                b += str.encode('\r\n\r\n{}\r\n'.format(file_path))
            # Otherwise load the file
            else:
                b += str.encode('filename="{}"\r\n'.format(Path(file_path).name) +
                                'Content-Type: {}\r\n\r\n'.format(file_type))
                if not file_path == '':
                    b += Path(file_path).read_bytes() + str.encode('\r\n')
            b + str.encode('\r\n')
        b += str.encode('--{}--\r\n'.format(boundry))

        filesize = len(b)
        h = [('Content-Type', 'multipart/form-data; boundary={}'.format(boundry)),
             ('Content-Length', str(filesize)),
             ('Connection', 'keep-alive')]
        return h, b

    def upload_metadata(self):

        ### A
        # Check the page for uploading metadata
        self.getPage('/upload/upload_page', self.cookies)
        self.assertStatus('200 OK')
        self.getPage('/upload/upload_metadata?studyType=qiime&studyName=Test_Server', self.cookies)
        self.assertStatus('200 OK')
        # Check an invalid metadata filetype
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_GZ], ['application/gzip'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'upload_metadata_file.html', title='Upload Metadata', user=self.server_user)
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
        page = load_html(fig.HTML_DIR / 'upload_metadata_warning.html', title='Warnings', user=self.server_user)
        warning = '31\t3\tStdDev Warning: Value 25.0 outside of two standard deviations of mean in column 3'
        page = insert_warning(page, 22, warning)
        self.assertBody(page)
        log('Checked metadata that warns')

        # Check a metadata file that has no issues
        headers, body = self.upload_files(['myMetaData'], [fig.TEST_METADATA_SHORTEST], ['text/tab-seperated-values'])
        self.getPage('/analysis/validate_metadata', headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'upload_data_files.html', title='Upload Data', user=self.server_user)
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

        # Search arguments for retrieving emails with access codes
        upload_args = [
            ['FROM', fig.MMEDS_EMAIL],
            ['TEXT', 'user {} uploaded data'.format(self.server_user)]
        ]

        mail = recieve_email(1, True, upload_args)
        code = mail[0].get_payload(decode=True).decode('utf-8')
        self.access_code = code.split('access code:')[1].splitlines()[1]

    def modify_upload(self):
        headers, body = self.upload_files(['myData'], [fig.TEST_READS], ['application/gzip'])
        self.getPage('/upload/modify_upload?data_type=for_reads&access_code=badcode',
                     headers + self.cookies, 'POST', body)
        self.assertStatus('200 OK')
        orig_page = load_html(fig.HTML_DIR / 'upload_select_page.html', title='Upload Type', user=self.server_user)
        err_page = insert_error(orig_page, 22, err.MissingUploadError().message)
        self.assertBody(err_page)
        self.getPage('/upload/modify_upload?data_type=for_reads&access_code={}'.format(self.access_code),
                     headers + self.cookies, 'POST', body)
        page = load_html(fig.HTML_DIR / 'welcome.html', title='Welcome to MMEDS', user=self.server_user)
        page = insert_html(page, 22, 'Upload modification successful')
        self.assertStatus('200 OK')
        self.assertBody(page)

    def download_page_fail(self):
        self.getPage("/auth/login?username={}&password={}".format(self.server_user, sec.TEST_PASS))
        self.getPage("/download/download_page?access_code={}".format(self.server_code + 'garbage'),
                     headers=self.cookies)
        self.assertStatus('200 OK')
        page = load_html(fig.HTML_DIR / 'welcome.html', title='Welcome to MMEDS', user=self.server_user)
        page = insert_error(page, 22, err.MissingUploadError.message)
        self.assertBody(page)
        self.getPage('/auth/logout', headers=self.cookies)

    def download_block(self):
        # Login
        self.getPage("/auth/login?username={}&password={}".format(self.server_user, sec.TEST_PASS))
        # Start test analysis
        self.getPage('/analysis/run_analysis?access_code={}&tool={}&config='.format(self.access_code,
                                                                                    fig.TEST_TOOL),
                     headers=self.cookies)

        # Wait for analysis to finish
        sleep(int(fig.TEST_TOOL.split('-')[-1]))

        # Try to access again
        self.getPage("/download/download_page?access_code={}".format(self.access_code), headers=self.cookies)

        page = load_html(fig.HTML_DIR / 'download_select_file.html',
                         user=self.server_user, title='Select Download')
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

    def lab_download(self):
        # Login
        self.getPage("/auth/logout", headers=self.cookies)
        self.assertStatus('200 OK')
        self.getPage("/auth/login?username={}&password={}".format(self.lab_user, sec.TEST_PASS))
        self.assertStatus('200 OK')
        self.getPage("/download/select_study", headers=self.cookies)
        self.assertStatus('200 OK')
        self.getPage("/download/download_study?study_code={}".format(self.access_code), headers=self.cookies)
        self.assertStatus('200 OK')
        metadata_path = self.body.decode('utf-8').split('\n')[33].split('"')[1]
        print(metadata_path)
        self.getPage("/download/download_filepath?file_path={}".format(metadata_path), headers=self.cookies)
        self.assertStatus('200 OK')

