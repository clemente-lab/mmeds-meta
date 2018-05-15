import os

import cherrypy as cp
from cherrypy.lib import static
from mmeds.mmeds import insert_error, validate_mapping_file
from mmeds.config import CONFIG, UPLOADED_FP, ERROR_FP, STORAGE_DIR
from mmeds.authentication import validate_password, check_username, check_password, add_user
from mmeds.database import Database

localDir = os.path.dirname(__file__)
absDir = os.path.join(os.getcwd(), localDir)


class MMEDSserver(object):

    def __init__(self):
        self.db = Database(STORAGE_DIR)

    @cp.expose
    def index(self):
        """ Home page of the application """
        return open('../html/index.html')

    @cp.expose
    def validate(self, myFile):
        """ The page returned after a file is uploaded. """

        # If nothing is uploaded proceed to the next page
        if myFile.filename == '':
            cp.log('No file uploaded')
            # Get the html for the upload page
            with open('../html/success.html', 'r') as f:
                upload_successful = f.read()
            return upload_successful

        # Otherwise check the file that's uploaded
        valid_extensions = ['txt', 'csv', 'tsv']
        file_extension = myFile.filename.split('.')[-1]
        if file_extension not in valid_extensions:
            with open('../html/upload.html') as f:
                page = f.read()
            return insert_error(page, 14, 'Error: ' + file_extension + ' is not a valid filetype.')

        cp.session['file'] = myFile.filename
        file_copy = os.path.join(STORAGE_DIR, 'copy_' + cp.session['file'])

        # Write the data to a new file stored on the server
        nf = open(file_copy, 'wb')
        while True:
            data = myFile.file.read(8192)
            nf.write(data)
            if not data:
                break
        nf.close()
        # Check the metadata file for errors
        with open(file_copy) as f:
            errors = validate_mapping_file(f)
            ########### TEMPORARY #############
            errors = []
            ##################################
            # errors += self.db.check_file_header(file_copy)

        # If there are errors report them and return the error page
        if len(errors) > 0:
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
        # Otherwise upload the metadata to the database
        else:
            # Get the html for the upload page
            with open('../html/success.html', 'r') as f:
                upload_successful = f.read()
            return upload_successful

    @cp.expose
    def query(self, query):
        # Set the session to use the current user
        with Database(STORAGE_DIR, user='mmeds_user') as db:
            username = cp.session['user']
            status = db.set_mmeds_user(username)
            cp.log('Set user to {}. Status {}'.format(username, status))
            result = db.execute(query)
            with open('../html/success.html', 'r') as f:
                page = f.read()

            page = insert_error(page, 10, result)
        return page

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
            return page.format(user=username)
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
