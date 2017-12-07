import os
import os.path

import cherrypy as cp
from cherrypy.lib import static
from mmeds.mmeds import insert_error, validate_mapping_file
from mmeds.config import CONFIG
from mmeds.authentication import validate_password, check_username, check_password, add_user

localDir = os.path.dirname(__file__)
absDir = os.path.join(os.getcwd(), localDir)

UPLOADED_FP = 'uploaded_file'
ERROR_FP = 'error_log.csv'
STORAGE_DIR = 'data/'


class MMEDSserver(object):

    @cp.expose
    def index(self):
        """ Home page of the application """
        return open('../html/index.html')

    @cp.expose
    def validate(self, myFile):
        """ The page returned after a file is uploaded. """

        valid_extensions = ['txt', 'csv', 'tsv']
        file_extension = myFile.filename.split('.')[-1]
        if file_extension not in valid_extensions:
            with open('../html/upload.html') as f:
                page = f.read()
            return insert_error(page, 14, 'Error: ' + file_extension + ' is not a valid filetype.')

        cp.session['file'] = myFile.filename

        # Write the data to a new file stored on the server
        nf = open(STORAGE_DIR + 'copy_' + cp.session['file'], 'wb')
        while True:
            data = myFile.file.read(8192)
            nf.write(data)
            if not data:
                break
        nf.close()

        with open(STORAGE_DIR + 'copy_' + cp.session['file']) as f:
            errors = validate_mapping_file(f)

        # Write the errors to a file
        with open(STORAGE_DIR + 'errors_' + cp.session['file'], 'w') as f:
            f.write('\n'.join(errors))

        # Get the html for the upload page
        with open('../html/error.html', 'r') as f:
            uploaded_output = f.read()

        uploaded_output = insert_error(uploaded_output, 7, '<h3>' + cp.session['user'] + '</h3>')
        for i, error in enumerate(errors):
            uploaded_output = insert_error(uploaded_output, 8 + i, '<p>' + error + '</p>')

        return uploaded_output

    @cp.expose
    def sign_up_page(self):
        """ Return the page for signing up. """
        return open('../html/sign_up_page.html')

    @cp.expose
    def sign_up(self, username, password1, password2):
        """
        Perform the actions necessary to sign up a new user.
        """
        pass_err = check_password(password1, password2)
        user_err = check_username(username)
        if pass_err:
            with open('../html/sign_up_page.html') as f:
                page = f.read()
            return insert_error(page, 25, pass_err)
        elif user_err:
            with open('../html/sign_up_page.html') as f:
                page = f.read()
            return insert_error(page, 25, user_err)
        else:
            add_user(username, password1)
            with open('../html/index.html') as f:
                page = f.read()
            return page

    @cp.expose
    def login(self, username, password):
        """
        Opens the page to upload files if the user has been authenticated.
        Otherwise returns to the login page with an error message.
        """
        cp.session['user'] = username
        if validate_password(username, password):
            with open('../html/upload.html') as f:
                page = f.read()
            return page.format(user=cp.session['user'])
        else:
            with open('../html/index.html') as f:
                page = f.read()
            return insert_error(page, 23, 'Error: Invalid username or password.')

    # View files
    @cp.expose
    def view_corrections(self):
        """ Page containing the marked up metadata as an html file """
        return open(STORAGE_DIR + UPLOADED_FP + '.html')

    @cp.expose
    def download_error_log(self):
        path = os.path.join(absDir, STORAGE_DIR + 'error_' + cp.session['file'])
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

    # Download links
    @cp.expose
    def download_log(self):
        """ Allows the user to download a log file """
        path = os.path.join(absDir, STORAGE_DIR + UPLOADED_FP + '.log')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

    @cp.expose
    def download_corrected(self):
        """ Allows the user to download the correct metadata file. """
        path = os.path.join(absDir, STORAGE_DIR + UPLOADED_FP + '_corrected.txt')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))


def secureheaders():
    headers = cp.response.headers
    headers['X-Frame-Options'] = 'DENY'
    headers['X-XSS-Protection'] = '1; mode=block'
    headers['Content-Security-Policy'] = 'default-src=self'
    if cp.server.ssl_certificate and cp.server.ssl_private_key:
        headers['Strict-Transport-Security'] = 'max-age=315360000'  # One Year


if __name__ == '__main__':
    cp.tools.secureheaders = cp.Tool('before_finalize', secureheaders, priority=60)
    cp.quickstart(MMEDSserver(), config=CONFIG)
