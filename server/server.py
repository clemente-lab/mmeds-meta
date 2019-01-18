import os
from pathlib import Path
from subprocess import run
from sys import argv

import cherrypy as cp
import mmeds.config as fig
import mmeds.secrets as sec
from cherrypy.lib import static
from mmeds import mmeds
from mmeds.mmeds import (send_email,
                         generate_error_html,
                         insert_html,
                         insert_error,
                         insert_warning,
                         validate_mapping_file,
                         create_local_copy)
from mmeds.config import CONFIG, UPLOADED_FP, DATABASE_DIR, HTML_DIR, USER_FILES
from mmeds.authentication import (validate_password,
                                  check_username,
                                  check_password,
                                  add_user,
                                  reset_password,
                                  change_password)
from mmeds.database import Database
from mmeds.tools import spawn_analysis
from mmeds.error import MissingUploadError, MetaDataError, LoggedOutError

absDir = Path(os.getcwd())


class MMEDSserver(object):

    def __init__(self, testing=False):
        self.db = None
        self.processes = {}
        self.testing = bool(int(testing))

    @cp.expose
    def get_user(self):
        """
        Return the current user. Delete them from the
        user list if session data is unavailable.
        """
        try:
            return cp.session['user']
        except KeyError as e:
            raise LoggedOutError(e.args[0])

    @cp.expose
    def index(self):
        """ Home page of the application """
        if cp.session.get('user'):
            page = mmeds.load_html('welcome',
                                   title='Welcome to Mmeds',
                                   user=cp.session['user'])
        else:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    ########################################
    #              Validation              #
    ########################################

    @cp.expose
    def run_analysis(self, access_code, tool, config):
        """
        Run analysis on the specified study
        ----------------------------------------
        :access_code: The code that identifies the dataset to run the tool on
        :tool: The tool to run on the chosen dataset
        """
        try:
            if self.processes.get(access_code) is None or\
                    self.processes[access_code].exitcode is not None:
                if 'qiime' in tool or 'test' in tool:
                    try:
                        cp.log('Running analysis with ' + tool)
                        if config.file is None:
                            p = spawn_analysis(tool, self.get_user(), access_code, None, self.testing)
                        else:
                            p = spawn_analysis(tool,
                                               self.get_user(),
                                               access_code,
                                               config.file.read().decode('utf-8'),
                                               self.testing)
                            self.processes[access_code] = p
                        page = mmeds.load_html('welcome',
                                               title='Welcome to Mmeds',
                                               user=self.get_user())
                        return page
                    except MissingUploadError:
                        page = mmeds.load_html('download_error',
                                               title='Download Error',
                                               user=self.get_user())
                        return page.format(self.get_user())
                else:
                    page = mmeds.load_html('welcome',
                                           title='Welcome to Mmeds',
                                           user=self.get_user())
                    page = insert_error(page, 31, 'Requested study is currently unavailable')
                    return page.format(user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
            return page

    # View files
    @cp.expose
    def view_corrections(self):
        """ Page containing the marked up metadata as an html file """
        return open(cp.session['dir'] / (UPLOADED_FP + '.html'))

    @cp.expose
    def validate_qiime(self, myMetaData, reads, barcodes, public='off'):
        """ The page returned after a file is uploaded. """
        try:
            # Check the file that's uploaded
            valid_extensions = ['txt', 'csv', 'tsv', 'zip', 'tar', 'tar.gz']
            file_extension = myMetaData.filename.split('.')[-1]
            if file_extension not in valid_extensions:
                page = mmeds.load_html('upload', title='Upload data')
                return insert_error(page, 14, 'Error: ' + file_extension + ' is not a valid filetype.')
            # Specify a particular test directory
            if fig.TEST_USER in self.get_user():
                ID = self.get_user().strip(fig.TEST_USER)
                new_dir = Path(str(fig.TEST_DIR) + ID)
                cp.log(str(new_dir))
                if not os.path.exists(new_dir):
                    os.makedirs(new_dir)
                    cp.log('Created dir {}'.format(new_dir))
            else:
                # Create a unique dir for handling files uploaded by this user
                count = 0
                new_dir = DATABASE_DIR / ('{}_{}'.format(self.get_user(), count))
                while os.path.exists(new_dir):
                    new_dir = DATABASE_DIR / ('{}_{}'.format(self.get_user(), count))
                    while os.path.exists(new_dir):
                        new_dir = DATABASE_DIR / ('{}_{}'.format(self.get_user(), count))
                        count += 1
                    os.makedirs(new_dir)
                cp.session['dir'] = new_dir
                cp.log('New directory for {}: {}'.format(self.get_user(), cp.session['dir']))

                # Create a copy of the Data file
                if reads.file is not None:
                    reads_copy = create_local_copy(reads.file, reads.filename, cp.session['dir'])
                else:
                    reads_copy = None

                # Create a copy of the Data file
                if barcodes.file is not None:
                    barcodes_copy = create_local_copy(barcodes.file, barcodes.filename, cp.session['dir'])
                else:
                    barcodes_copy = None

                # Create a copy of the MetaData
                metadata_copy = create_local_copy(myMetaData.file, myMetaData.filename, cp.session['dir'])

                # Set the User
                if public == 'on':
                    username = 'public'
                else:
                    username = self.get_user()

                # Check the metadata file for errors
                errors, warnings, study_name, subjects = validate_mapping_file(metadata_copy)
                for error in errors:
                    cp.log(error)

                with Database(cp.session['dir'], owner=username, testing=self.testing) as db:
                    try:
                        warnings += db.check_repeated_subjects(subjects)
                        errors += db.check_user_study_name(study_name)
                    except MetaDataError as e:
                        errors.append('-1\t-1\t' + e.message)

                # If there are errors report them and return the error page
                if len(errors) > 0:
                    cp.session['error_file'] = cp.session['dir'] / ('errors_' + str(myMetaData.filename))
                    # Write the errors to a file
                    with open(cp.session['error_file'], 'w') as f:
                        f.write('\n'.join(errors + warnings))

                    uploaded_output = mmeds.load_html('error', title='Errors')
                    uploaded_output = insert_error(
                        uploaded_output, 7, '<h3>' + self.get_user() + '</h3>')
                    for i, warning in enumerate(warnings):
                        uploaded_output = insert_warning(uploaded_output, 22 + i, warning)
                    for i, error in enumerate(errors):
                        uploaded_output = insert_error(uploaded_output, 22 + i, error)

                    html = generate_error_html(metadata_copy, errors, warnings)
                    cp.log('Created error html')

                    return html
                elif len(warnings) > 0:
                    cp.session['uploaded_files'] = [metadata_copy, reads_copy, barcodes_copy, username]
                    # Write the errors to a file
                    with open(cp.session['dir'] / ('warnings_' + myMetaData.filename), 'w') as f:
                        f.write('\n'.join(warnings))

                    # Get the html for the upload page
                    uploaded_output = mmeds.load_html('warning', title='Warnings')

                    for i, warning in enumerate(warnings):
                        uploaded_output = insert_warning(uploaded_output, 22 + i, warning)

                    return uploaded_output
                else:
                    # Otherwise upload the metadata to the database
                    os.mkdir(cp.session['dir'] / 'database_files')
                    with Database(cp.session['dir'] / 'database_files', owner=username, testing=self.testing) as db:
                        access_code, study_name, email = db.read_in_sheet(metadata_copy,
                                                                          'qiime',
                                                                          reads=reads_copy,
                                                                          barcodes=barcodes_copy)

                    # Send the confirmation email
                    send_email(email, username, code=access_code, testing=self.testing)

                    # Get the html for the upload page
                    page = mmeds.load_html('welcome',
                                           title='Welcome to Mmeds',
                                           user=self.get_user())
                    return page
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
            return page

    @cp.expose
    def proceed_with_warning(self):
        """ Proceed with upload after recieving a/some warning(s). """
        try:
            metadata_copy, data_copy1, data_copy2, username = cp.session['uploaded_files']
            # Otherwise upload the metadata to the database
            cp.log(str(cp.session['dir']))
            os.mkdir(cp.session['dir'] / 'database_files')
            with Database(cp.session['dir'] / 'database_files', owner=username, testing=self.testing) as db:
                access_code, study_name, email = db.read_in_sheet(metadata_copy,
                                                                  'qiime',
                                                                  reads=data_copy1,
                                                                  barcodes=data_copy2)

            # Send the confirmation email
            send_email(email, username, code=access_code, testing=self.testing)

            # Get the html for the upload page
            page = mmeds.load_html('welcome',
                                   title='Welcome to Mmeds',
                                   user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    ########################################
    #            Authentication            #
    ########################################

    @cp.expose
    def reset_code(self, study_name, study_email):
        """ Skip uploading a file. """
        try:
            # Get the open file handler
            with Database(cp.session['dir'], owner=self.get_user(), testing=self.testing) as db:
                try:
                    db.reset_access_code(study_name, study_email)
                    page = mmeds.load_html('success', title='Success', user=self.get_user())
                except MissingUploadError:
                    page = mmeds.load_html('download_error', title='Download Error', user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def query(self, query):
        try:
            # Set the session to use the current user
            username = self.get_user()
            with Database(cp.session['dir'], user=sec.SQL_DATABASE_USER, owner=username, testing=self.testing) as db:
                data, header = db.execute(query)
                html_data = db.format(data, header)
                page = mmeds.load_html('success', title='Run Query', user=self.get_user())

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
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

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
            with open(HTML_DIR / 'sign_up_page.html') as f:
                page = f.read()
            return insert_error(page, 25, pass_err)
        elif user_err:
            with open(HTML_DIR / 'sign_up_page.html') as f:
                page = f.read()
            return insert_error(page, 25, user_err)
        else:
            add_user(username, password1, email, testing=self.testing)
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
            return page

    @cp.expose
    def login(self, username, password):
        """
        Opens the page to upload files if the user has been authenticated.
        Otherwise returns to the login page with an error message.
        """
        cp.log('Login attempt for user: {}'.format(username))

        if not validate_password(username, password, testing=self.testing):
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
            cp.log('Login Error: Invalid username or password')
            return insert_error(page, 23, 'Error: Invalid username or password.')
        else:
            cp.session['user'] = username
            self.processes = {}
            page = mmeds.load_html('welcome',
                                   title='Welcome to Mmeds',
                                   user=self.get_user())
            cp.log('Login Successful')
            return page.format(user=username)

    @cp.expose
    def home(self):
        """ Return the home page of the server for a user already logged in. """
        try:
            page = mmeds.load_html('welcome',
                                   title='Welcome to Mmeds',
                                   user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def logout(self):
        """ Expires the session and returns to login page """
        cp.log('Logout user {}'.format(cp.session['user']))
        cp.lib.sessions.expire()
        return open(HTML_DIR / 'index.html')

    @cp.expose
    def input_password(self):
        """ Load page for changing the user's password """
        try:
            page = mmeds.load_html('change_password', title='Change Password')
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def change_password(self, password0, password1, password2):
        """
        Change the user's password
        ===============================
        :password0: The old password
        :password1: The new password
        :password2: A second entry of the new password
        """
        try:
            page = mmeds.load_html('change_password', title='Change Password')

            # Check the old password matches
            if validate_password(self.get_user(), password0):
                # Check the two copies of the new password match
                errors = check_password(password1, password2)
                if len(errors) == 0:
                    change_password(self.get_user(), password1)
                    page = insert_html(page, 9, '<h4> Your password was successfully changed. </h4>')
                else:
                    page = insert_html(page, 9, errors)
            else:
                page = insert_html(page, 9, '<h4> The given current password is incorrect. </h4>')
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    ########################################
    #             Upload Pages             #
    ########################################

    @cp.expose
    def upload(self, study_type):
        """ Page for uploading Qiime data """
        try:
            if 'qiime' in study_type:
                page = mmeds.load_html('upload_qiime',
                                       title='Upload Qiime',
                                       user=self.get_user(),
                                       version=study_type)
            else:
                page = '<html> <h1> Sorry {user}, this page not available </h1> </html>'
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def retry_upload(self):
        """ Retry the upload of data files. """
        try:
            with open(HTML_DIR / 'upload.html') as f:
                page = f.read()
            page = page.format(user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def modify_upload(self, myData, access_code):
        """ Modify the data of an existing upload. """
        try:
            # Create a copy of the Data file
            data_copy = create_local_copy(myData.file, myData.filename)

            with Database(cp.session['dir'], owner=self.get_user(), testing=self.testing) as db:
                try:
                    db.modify_data(data_copy, access_code)
                except MissingUploadError:
                    with open(HTML_DIR / 'download_error.html') as f:
                        download_error = f.read()
                    return download_error.format(self.get_user())
            # Get the html for the upload page
            with open(HTML_DIR / 'success.html', 'r') as f:
                page = f.read()
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def convert_metadata(self, convertTo, myMetaData, unitCol, skipRows):
        """
        Convert the uploaded MIxS metadata file to a mmeds metadata file and return it.
        """
        try:
            meta_copy = create_local_copy(myMetaData.file, myMetaData.filename, cp.session['dir'])
            # Try the conversion
            try:
                if convertTo == 'mmeds':
                    file_path = cp.session['dir'] / 'mmeds_metadata.tsv'
                    # If it is successful return the converted file
                    mmeds.MIxS_to_mmeds(meta_copy, file_path, skip_rows=skipRows, unit_column=unitCol)
                else:
                    file_path = cp.session['dir'] / 'mixs_metadata.tsv'
                    mmeds.mmeds_to_MIxS(meta_copy, file_path, skip_rows=skipRows, unit_column=unitCol)
                page = static.serve_file(file_path, 'application/x-download',
                                         'attachment', os.path.basename(file_path))
            # If there is an issue with the provided unit column display an error
            except MetaDataError as e:
                page = mmeds.load_html('welcome',
                                       title='Welcome to Mmeds',
                                       user=self.get_user())
                page = insert_error(page, 31, e.message)
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    ########################################
    #            No Logic Pages            #
    ########################################

    @cp.expose
    def query_page(self):
        """ Skip uploading a file. """
        try:
            # Get the html for the upload page
            page = mmeds.load_html('success', title='Skipped Upload')
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def analysis_page(self):
        """ Page for running analysis of previous uploads. """
        try:
            page = mmeds.load_html('analysis', title='Select Analysis', user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def upload_page(self):
        """ Page for selecting upload type or modifying upload. """
        try:
            page = mmeds.load_html('upload', title='Upload Data', user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def sign_up_page(self):
        """ Return the page for signing up. """
        return open(HTML_DIR / 'sign_up_page.html')

    ########################################
    #            Download Pages            #
    ########################################

    @cp.expose
    def download_page(self, access_code):
        """ Loads the page with the links to download data and metadata. """
        try:
            if self.processes.get(access_code) is None or\
                    self.processes[access_code].exitcode is not None:
                # Get the open file handler
                with Database(path='.', owner=self.get_user(), testing=testing) as db:
                    try:
                        files, path = db.get_mongo_files(access_code)
                    except MissingUploadError as e:
                        cp.log(str(e))
                        return mmeds.load_html('download_error', title='Download Error', user=self.get_user())

                page = mmeds.load_html('select_download', title='Select Download', user=self.get_user())

                i = 0
                for f in files.keys():
                    if f in USER_FILES:
                        page = insert_html(page, 24 + i, '<option value="{}">{}</option>'.format(f, f))
                        i += 1

                cp.session['download_access'] = access_code
            else:
                page = mmeds.load_html('welcome', title='Welcome', user=self.get_user())
                page = insert_error(page, 22, 'Requested study is currently unavailable')
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def select_download(self, download):
        try:
            cp.log('User{} requests download {}'.format(self.get_user(), download))
            with Database('.', owner=self.get_user(), testing=testing) as db:
                try:
                    files, path = db.get_mongo_files(cp.session['download_access'])
                except MissingUploadError as e:
                    cp.log(e)
                    return mmeds.load_html('download_error',
                                           title='Download Error',
                                           user=self.get_user())

            file_path = str(Path(path) / files[download])
            if 'dir' in download:
                run('tar -czvf {} -C {} {}'.format(file_path + '.tar.gz',
                                                   Path(file_path).parent,
                                                   Path(file_path).name),
                    shell=True,
                    check=True)
                file_path += '.tar.gz'
            cp.log('Fetching {}'.format(file_path))

            page = static.serve_file(file_path, 'application/x-download',
                                     'attachment', os.path.basename(file_path))
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def download_metadata(self):
        """ Download data and metadata files. """
        try:
            # Return that file
            page = static.serve_file(cp.session['metadata_path'], 'application/x-download',
                                     'attachment', os.path.basename(cp.session['metadata_path']))
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def download_data(self):
        """ Download data and metadata files. """
        # Return that file
        try:
            page = static.serve_file(cp.session['data_path'], 'application/x-download',
                                     'attachment', os.path.basename(cp.session['data_path']))
        except KeyError:
            page = mmeds.load_html('download_error', title='Download Error', user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def password_recovery(self, username, email):
        """ Page for reseting a user's password. """
        with open(HTML_DIR / 'blank.html') as f:
            page = f.read()
        if username == 'Public' or username == 'public':
            page = insert_html(
                page, 10, '<h4> No account exists with the providied username and email. </h4>')
            return page
        exit = reset_password(username, email)

        if exit:
            page = insert_html(page, 10, '<h4> A new password has been sent to your email. </h4>')
        else:
            page = insert_html(
                page, 10, '<h4> No account exists with the providied username and email. </h4>')
        return page

    @cp.expose
    def download_error_log(self):
        try:
            page = static.serve_file(cp.session['error_file'], 'application/x-download',
                                     'attachment', os.path.basename(cp.session['error_file']))
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def download_log(self):
        """ Allows the user to download a log file """
        try:
            path = cp.session['dir'] / (UPLOADED_FP + '.log')
            page = static.serve_file(path, 'application/x-download',
                                     'attachment', os.path.basename(path))
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def download_corrected(self):
        """ Allows the user to download the correct metadata file. """
        try:
            path = cp.session['dir'] / (UPLOADED_FP + '_corrected.txt')
            page = static.serve_file(path, 'application/x-download',
                                     'attachment', os.path.basename(path))
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def download_query(self):
        """ Download the results of the most recent query as a csv. """
        try:
            path = cp.session['dir'] / cp.session['query']
            page = static.serve_file(path, 'application/x-download',
                                     'attachment', os.path.basename(path))
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page


def secureheaders():
    headers = cp.response.headers
    headers['X-Frame-Options'] = 'DENY'
    headers['X-XSS-Protection'] = '1; mode=block'
    headers['Content-Security-Policy'] = 'default-src=self'
    if cp.server.ssl_certificate and cp.server.ssl_private_key:
        headers['Strict-Transport-Security'] = 'max-age=315360000'  # One Year


if __name__ == '__main__':
    try:
        testing = argv[1]
    except IndexError:
        testing = False
    cp.tools.secureheaders = cp.Tool('before_finalize', secureheaders, priority=60)
    cp.quickstart(MMEDSserver(testing), config=CONFIG)
