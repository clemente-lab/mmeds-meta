import os
from pathlib import Path
from shutil import rmtree
from glob import glob
from subprocess import run

import cherrypy as cp
from cherrypy.lib import static
from mmeds.mmeds import generate_error_html, insert_html, insert_error, insert_warning, validate_mapping_file, create_local_copy
from mmeds.config import CONFIG, UPLOADED_FP, STORAGE_DIR, send_email, get_salt
from mmeds.authentication import validate_password, check_username, check_password, add_user, reset_password, change_password
from mmeds.database import Database
from mmeds.tools import analysis_runner
from mmeds.error import MissingUploadError

absDir = Path(os.getcwd())


class MMEDSserver(object):

    def __init__(self):
        self.db = None

    def __del__(self):
        temp_dirs = glob(STORAGE_DIR + 'temp_*')
        for temp in temp_dirs:
            cp.log('Removing temporary dir ' + temp)
            rmtree(temp)

    @cp.expose
    def index(self):
        """ Home page of the application """
        return open('../html/index.html')

    ########################################
    #############  Validation  #############
    ########################################

    @cp.expose
    def run_analysis(self, access_code, tool):
        """ Run analysis on the specified study. """
        if tool == 'qiime':
            try:
                analysis_runner('qiime', cp.session['user'], access_code)
                with open('../html/welcome.html') as f:
                    page = f.read()
                return page
            except MissingUploadError:
                with open('../html/download_error.html') as f:
                    page = f.read()
                return page.format(cp.session['user'])
        else:
            return "<html> <h1> Tool does not exist. </h1> </html>"

    # View files
    @cp.expose
    def view_corrections(self):
        """ Page containing the marked up metadata as an html file """
        return open(cp.session['dir'] / (UPLOADED_FP + '.html'))

    @cp.expose
    def validate_qiime(self, myMetaData, reads, barcodes, public='off'):
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
            reads_copy = create_local_copy(reads.file, reads.filename, cp.session['dir'])
        # Except the error if there is no file
        except AttributeError:
            reads_copy = None

        # Create a copy of the Data file
        try:
            barcodes_copy = create_local_copy(barcodes.file, barcodes.filename, cp.session['dir'])
        # Except the error if there is no file
        except AttributeError:
            barcodes_copy = None

        # Create a copy of the MetaData
        metadata_copy = create_local_copy(myMetaData.file, myMetaData.filename, cp.session['dir'])

        # Set the User
        if public == 'on':
            username = 'public'
        else:
            username = cp.session['user']

        # Check the metadata file for errors
        with open(metadata_copy) as f:
            errors, warnings, study_name, subjects = validate_mapping_file(f)
        cp.log(study_name)

        with Database(cp.session['dir'], user='root', owner=username) as db:
            warnings += db.check_repeated_subjects(subjects)
            errors += db.check_user_study_name(study_name)

        # If there are errors report them and return the error page
        if len(errors) > 0:
            cp.session['error_file'] = cp.session['dir'] / 'errors_' + str(myMetaData.filename)
            # Write the errors to a file
            with open(cp.session['error_file'], 'w') as f:
                f.write('\n'.join(errors + warnings))

            # Get the html for the upload page
            with open('../html/error.html', 'r') as f:
                uploaded_output = f.read()

            uploaded_output = insert_error(uploaded_output, 7, '<h3>' + cp.session['user'] + '</h3>')
            for i, error in enumerate(errors):
                uploaded_output = insert_error(uploaded_output, 8 + i, '<p>' + error + '</p>')
            for i, warning in enumerate(warnings):
                uploaded_output = insert_warning(uploaded_output, 8 + i, '<p>' + warning + '</p>')

            html = generate_error_html(metadata_copy, errors, warnings)

            return html
        elif len(warnings) > 0:
            cp.session['uploaded_files'] = [metadata_copy, reads_copy, barcodes_copy, username]
            # Write the errors to a file
            with open(cp.session['dir'] / ('errors_' + myMetaData.filename), 'w') as f:
                f.write('\n'.join(errors))

            # Get the html for the upload page
            with open('../html/warning.html', 'r') as f:
                uploaded_output = f.read()

            for i, warning in enumerate(warnings):
                uploaded_output = insert_warning(uploaded_output, 8 + i, '<p>' + warning + '</p>')

            uploaded_output = insert_error(uploaded_output, 7, '<h3>' + cp.session['user'] + '</h3>')
            return uploaded_output
        else:
            # Otherwise upload the metadata to the database
            with Database(cp.session['dir'], user='root', owner=username) as db:
                access_code, study_name, email = db.read_in_sheet(metadata_copy,
                                                                  'qiime',
                                                                  reads=reads_copy,
                                                                  barcodes=barcodes_copy)

            # Send the confirmation email
            send_email(email, username, code=access_code)

            # Update the directory
            cp.session['uploaded'] = True
            #new_dir = Path(str(cp.session['dir']).replace('temp', 'upload'))
            #os.rename(cp.session['dir'], new_dir)
            #cp.session['dir'] = new_dir

            # Get the html for the upload page
            with open('../html/welcome.html', 'r') as f:
                upload_successful = f.read()
            return upload_successful.format(user=cp.session['user'])

    @cp.expose
    def proceed_with_warning(self):
        """ Proceed with upload after recieving a/some warning(s). """
        metadata_copy, data_copy1, data_copy2, username = cp.session['uploaded_files']
        # Otherwise upload the metadata to the database
        cp.log(str(cp.session['dir']))
        with Database(cp.session['dir'], user='root', owner=username) as db:
            access_code, study_name, email = db.read_in_sheet(metadata_copy,
                                                              'qiime',
                                                              reads=data_copy1,
                                                              barcodes=data_copy2)

        # Send the confirmation email
        send_email(email, username, code=access_code)

        # Update the directory
        cp.session['uploaded'] = True
        # new_dir = Path(str(cp.session['dir']).replace('temp', 'upload'))
        # os.rename(cp.session['dir'], new_dir)
        # cp.session['dir'] = new_dir

        # Get the html for the upload page
        with open('../html/welcome.html', 'r') as f:
            upload_successful = f.read()
        return upload_successful.format(user=cp.session['user'])

    ########################################
    ###########  Authentication  ###########
    ########################################

    @cp.expose
    def reset_code(self, study_name, study_email):
        """ Skip uploading a file. """
        # Get the open file handler
        with Database(cp.session['dir'], user='root', owner=cp.session['user']) as db:
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
        with Database(cp.session['dir'], user='mmeds_user', owner=username) as db:
            status = db.set_mmeds_user(username)
            cp.log('Set user to {}. Status {}'.format(username, status))
            data, header = db.execute(query)
            html_data = db.format(data, header)
            with open('../html/success.html', 'r') as f:
                page = f.read()

        cp.session['query'] = 'query.tsv'
        html = '<form action="download_query" method="post">\n\
                <button type="submit">Download Results</button>\n\
                </form>'
        page = insert_html(page, 10, html)
        page = insert_error(page, 10, html_data)
        if header is not None:
            data = [header] + list(data)
        with open(cp.session['dir'] / cp.session['query'], 'w') as f:
            f.write('\n'.join(list(map(lambda x: '\t'.join(list(map(str, x))), data))))
        return page

    @cp.expose
    def get_additional_mdata(self):
        """ Return the additional MetaData uploaded by the user. """
        pass

    @cp.expose
    def get_data(self):
        """ Return the data file uploaded by the user. """
        path = cp.session['dir'] / cp.session['data_file']
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

    @cp.expose
    def sign_up(self, username, password1, password2, email):
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
            add_user(username, password1, email)
            with open('../html/index.html') as f:
                page = f.read()
            return page

    @cp.expose
    def login(self, username, password):
        """
        Opens the page to upload files if the user has been authenticated.
        Otherwise returns to the login page with an error message.
        """
        cp.session['uploaded'] = False
        cp.session['user'] = username
        # Create a unique dir for handling files uploaded by this user
        new_dir = absDir / STORAGE_DIR / ('temp_' + get_salt(10))
        while os.path.exists(new_dir):
            new_dir = absDir / STORAGE_DIR / ('temp_' + get_salt(10))
        os.makedirs(new_dir)
        cp.session['dir'] = new_dir
        cp.log('Current directory for {}: {}'.format(username, cp.session['dir']))
        if validate_password(username, password):
            with open('../html/welcome.html') as f:
                page = f.read()
            return page.format(user=username)
        else:
            with open('../html/index.html') as f:
                page = f.read()
            return insert_error(page, 23, 'Error: Invalid username or password.')

    @cp.expose
    def logout(self):
        """
        Expires the session and returns to login page
        """
        cp.session['user'] = None
        if not cp.session['uploaded']:
            rmtree(cp.session['dir'])

        return open('../html/index.html')

    @cp.expose
    def input_password(self):
        """ Load page for changing the user's password """
        with open('../html/change_password.html') as f:
            page = f.read()
        return page

    @cp.expose
    def change_password(self, password0, password1, password2):
        """ Change the user's password """
        with open('../html/change_password.html') as f:
            page = f.read()

        # Check the old password matches
        if validate_password(cp.session['user'], password0):
            # Check the two copies of the new password match
            errors = check_password(password1, password2)
            if len(errors) == 0:
                change_password(cp.session['user'], password1)
                page = insert_html(page, 9, '<h4> Your password was successfully changed. </h4>')
            else:
                page = insert_html(page, 9, errors)
        else:
            page = insert_html(page, 9, '<h4> The given current password is incorrect. </h4>')
        return page

    ########################################
    ###########   Upload Pages   ###########
    ########################################

    @cp.expose
    def upload(self, study_type):
        """ Page for uploading Qiime data """
        if study_type == 'qiime':
            with open('../html/upload_qiime.html') as f:
                page = f.read()
        else:
            page = '<html> <h1> Sorry {user}, this page not available </h1> </html>'
        return page.format(user=cp.session['user'])

    @cp.expose
    def retry_upload(self):
        """ Retry the upload of data files. """
        with open('../html/upload.html') as f:
            page = f.read()
        return page.format(user=cp.session['user'])

    @cp.expose
    def modify_upload(self, myData, access_code):
        """ Modify the data of an existing upload. """
        # Create a copy of the Data file
        data_copy = create_local_copy(myData.file, myData.filename)

        with Database(cp.session['dir'], user='root', owner=cp.session['user']) as db:
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

    ########################################
    ###########  No Logic Pages  ###########
    ########################################

    @cp.expose
    def query_page(self):
        """ Skip uploading a file. """
        # Get the html for the upload page
        with open('../html/success.html', 'r') as f:
            upload_successful = f.read()
        return upload_successful

    @cp.expose
    def analysis_page(self):
        """ Page for running analysis of previous uploads. """
        with open('../html/analysis.html') as f:
            page = f.read()
        return page

    @cp.expose
    def upload_page(self):
        """ Page for selecting upload type or modifying upload. """
        with open('../html/upload.html') as f:
            page = f.read()
        return page.format(user=cp.session['user'])

    @cp.expose
    def sign_up_page(self):
        """ Return the page for signing up. """
        return open('../html/sign_up_page.html')

    ########################################
    ###########  Download Pages  ###########
    ########################################

    @cp.expose
    def download_page(self, access_code):
        """ Loads the page with the links to download data and metadata. """
        # Get the open file handler
        with Database(cp.session['dir'], user='root', owner=cp.session['user']) as db:
            try:
                files, path = db.get_mongo_files(access_code)
            except AttributeError as e:
                cp.log(e)
                with open('../html/download_error.html') as f:
                    download_error = f.read()
                return download_error.format(cp.session['user'])

        with open('../html/select_download.html') as f:
            page = f.read()

        for i, f in enumerate(files.keys()):
            page = insert_html(page, 10 + i, '<option value="{}">{}</option>'.format(f, f))

        cp.session['download_access'] = access_code
        return page

    @cp.expose
    def select_download(self, download):
        with Database(cp.session['dir'], user='root', owner=cp.session['user']) as db:
            try:
                files, path = db.get_mongo_files(cp.session['download_access'])
            except AttributeError as e:
                cp.log(e)
                with open('../html/download_error.html') as f:
                    download_error = f.read()
                return download_error.format(cp.session['user'])

        file_path = str(Path(path) / files[download])
        if 'dir' in download:
            run('tar -czvf {} {}'.format(file_path + '.tar.gz', file_path), shell=True, check=True)
            file_path += '.tar.gz'

        return static.serve_file(file_path, 'application/x-download',
                                 'attachment', os.path.basename(file_path))

    @cp.expose
    def download_metadata(self):
        """ Download data and metadata files. """
        # Return that file
        return static.serve_file(cp.session['metadata_path'], 'application/x-download',
                                 'attachment', os.path.basename(cp.session['metadata_path']))

    @cp.expose
    def download_data(self):
        """ Download data and metadata files. """
        # Return that file
        try:
            return static.serve_file(cp.session['data_path'], 'application/x-download',
                                     'attachment', os.path.basename(cp.session['data_path']))
        except KeyError:
            with open('../html/download_error.html') as f:
                page = f.read()
            return page.format(cp.session['user'])

    @cp.expose
    def password_recovery(self, username, email):
        """ Page for reseting a user's password. """
        with open('../html/blank.html') as f:
            page = f.read()
        if username == 'Public' or username == 'public':
            page = insert_html(page, 10, '<h4> No account exists with the providied username and email. </h4>')
            return page
        exit = reset_password(username, email)

        if exit:
            page = insert_html(page, 10, '<h4> A new password has been sent to your email. </h4>')
        else:
            page = insert_html(page, 10, '<h4> No account exists with the providied username and email. </h4>')
        return page

    @cp.expose
    def download_error_log(self):
        return static.serve_file(cp.session['error_file'], 'application/x-download',
                                 'attachment', os.path.basename(cp.session['error_file']))

    @cp.expose
    def download_log(self):
        """ Allows the user to download a log file """
        path = cp.session['dir'] / (UPLOADED_FP + '.log')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

    @cp.expose
    def download_corrected(self):
        """ Allows the user to download the correct metadata file. """
        path = cp.session['dir'] / (UPLOADED_FP + '_corrected.txt')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

    @cp.expose
    def download_query(self):
        """ Download the results of the most recent query as a csv. """

        path = cp.session['dir'] / cp.session['query']
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
