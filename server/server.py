import os

import cherrypy as cp
from cherrypy.lib import static
from mmeds.mmeds import insert_error, validate_mapping_file, create_local_copy
from mmeds.config import CONFIG, UPLOADED_FP, STORAGE_DIR, send_email
from mmeds.authentication import validate_password, check_username, check_password, add_user
from mmeds.database import Database

localDir = os.path.dirname(__file__)
absDir = os.path.join(os.getcwd(), localDir)


class MMEDSserver(object):

    def __init__(self):
        self.db = None

    @cp.expose
    def index(self):
        """ Home page of the application """
        return open('../html/index.html')

    @cp.expose
    def validate(self, myMetaData, myData, myEmail, public='off'):
        """ The page returned after a file is uploaded. """
        # Check the file that's uploaded
        valid_extensions = ['txt', 'csv', 'tsv']
        file_extension = myMetaData.filename.split('.')[-1]
        if file_extension not in valid_extensions:
            with open('../html/upload.html') as f:
                page = f.read()
            return insert_error(page, 14, 'Error: ' + file_extension + ' is not a valid filetype.')

        # Create a copy of the Data file
        try:
            data_copy = create_local_copy(myData.file, myData.filename)
        # Except the error if there is no file
        except AttributeError:
            data_copy = None

        # Create a copy of the MetaData
        metadata_copy = create_local_copy(myMetaData.file, myMetaData.filename)

        # Check the metadata file for errors
        with open(metadata_copy) as f:
            errors = validate_mapping_file(f)

        # If there are errors report them and return the error page
        if len(errors) > 0:
            # Write the errors to a file
            with open(STORAGE_DIR + 'errors_' + cp.session['metadata_file'], 'w') as f:
                f.write('\n'.join(errors))

            # Get the html for the upload page
            with open('../html/error.html', 'r') as f:
                uploaded_output = f.read()

            uploaded_output = insert_error(uploaded_output, 7, '<h3>' + cp.session['user'] + '</h3>')
            for i, error in enumerate(errors):
                uploaded_output = insert_error(uploaded_output, 8 + i, '<p>' + error + '</p>')

            return uploaded_output
        else:
            if public == 'on':
                username = 'public'
            else:
                username = cp.session['user']

            # Otherwise upload the metadata to the database
            with Database(STORAGE_DIR, user='root', owner=username) as db:
                access_code = db.read_in_sheet(metadata_copy, data_copy, myEmail)

            # Send the confirmation email
            send_email(myEmail, username, access_code)

            # Get the html for the upload page
            with open('../html/success.html', 'r') as f:
                upload_successful = f.read()
            return upload_successful

    @cp.expose
    def modify_upload(self, myData, access_code):
        """ Modify the data of an existing upload. """
        # Create a copy of the Data file
        data_copy = create_local_copy(myData.file, myData.filename)

        with Database(STORAGE_DIR, user='root', owner=cp.session['user']) as db:
            try:
                db.modify_data(data_copy, access_code)
            except AttributeError:
                with open('../html/download_error.html') as f:
                    download_error = f.read()
                return download_error.format(cp.session['user'])
        # Get the html for the upload page
        with open('../html/success.html', 'r') as f:
            upload_successful = f.read()
        return upload_successful

    @cp.expose
    def skip_upload(self):
        """ Skip uploading a file. """
        # Get the html for the upload page
        with open('../html/success.html', 'r') as f:
            upload_successful = f.read()
        return upload_successful

    @cp.expose
    def reset_code(self, study_name, study_email):
        """ Skip uploading a file. """
        # Get the open file handler
        with Database(STORAGE_DIR, user='root', owner=cp.session['user']) as db:
            try:
                db.reset_access_code(study_name, study_email)
            except AttributeError:
                with open('../html/download_error.html') as f:
                    download_error = f.read()
                return download_error.format(cp.session['user'])
        # Get the html for the upload page
        with open('../html/success.html', 'r') as f:
            upload_successful = f.read()
        return upload_successful

    @cp.expose
    def query(self, query):
        # Set the session to use the current user
        username = cp.session['user']
        with Database(STORAGE_DIR, user='mmeds_user', owner=username) as db:
            status = db.set_mmeds_user(username)
            cp.log('Set user to {}. Status {}'.format(username, status))
            result = db.execute(query)
            with open('../html/success.html', 'r') as f:
                page = f.read()

            page = insert_error(page, 10, result)
        return page

    @cp.expose
    def get_additional_mdata(self):
        """ Return the additional MetaData uploaded by the user. """
        pass

    @cp.expose
    def get_data(self):
        """ Return the data file uploaded by the user. """
        path = os.path.join(absDir, STORAGE_DIR + cp.session['data_file'])
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

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

    @cp.expose
    def download_data(self, access_code):
        """ Download data and metadata files. """
        # Get the open file handler
        with Database(STORAGE_DIR, user='root', owner=cp.session['user']) as db:
            try:
                fp = db.get_data_from_access_code(access_code)
            except AttributeError:
                with open('../html/download_error.html') as f:
                    download_error = f.read()
                return download_error.format(cp.session['user'])
        # Write the information to a static file
        with open(STORAGE_DIR + 'download.txt', 'wb') as f:
            f.write(fp.read())
        path = os.path.join(absDir, STORAGE_DIR + 'download.txt')
        # Return that file
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

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
