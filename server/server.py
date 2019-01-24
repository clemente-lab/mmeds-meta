import os
from pathlib import Path
from subprocess import run
from multiprocessing import Process
from sys import argv
import cherrypy as cp
import mmeds.secrets as sec
from cherrypy.lib import static
from mmeds import mmeds
from mmeds.mmeds import (generate_error_html,
                         insert_html,
                         insert_error,
                         insert_warning,
                         validate_mapping_file,
                         log,
                         create_local_copy)
from mmeds.config import CONFIG, UPLOADED_FP, DATABASE_DIR, HTML_DIR, USER_FILES
from mmeds.authentication import (validate_password,
                                  check_username,
                                  check_password,
                                  add_user,
                                  reset_password,
                                  change_password)
from mmeds.database import Database
from mmeds.spawn import spawn_analysis, handle_data_upload, handle_modify_data
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
        except KeyError:
            raise LoggedOutError('No user logged in')

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
        log('In run_analysis')
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
        log('In view_corrections')
        return open(cp.session['dir'] / (UPLOADED_FP + '.html'))

    @cp.expose
    def validate_metadata(self, myMetaData):
        """ The page returned after a file is uploaded. """
        log('In validate_metadata')
        try:
            # Check the file that's uploaded
            valid_extensions = ['txt', 'csv', 'tsv']
            file_extension = myMetaData.filename.split('.')[-1]
            if file_extension not in valid_extensions:
                page = mmeds.load_html('upload', title='Upload data')
                return insert_error(page, 14, 'Error: ' + file_extension + ' is not a valid filetype.')

            count = 0
            new_dir = DATABASE_DIR / ('{}_{}'.format(self.get_user(), count))
            while new_dir.is_dir():
                new_dir = DATABASE_DIR / ('{}_{}'.format(self.get_user(), count))
                count += 1
            new_dir.mkdir()
            cp.session['dir'] = new_dir
            log("Upload dir {}".format(new_dir))

            # Create a copy of the MetaData
            metadata_copy = create_local_copy(myMetaData.file, myMetaData.filename, new_dir)

            # Check the metadata file for errors
            errors, warnings, study_name, subjects = validate_mapping_file(metadata_copy)

            # The database for any issues with previous uploads
            with Database(new_dir, owner=self.get_user(), testing=self.testing) as db:
                try:
                    warnings += db.check_repeated_subjects(subjects)
                    errors += db.check_user_study_name(study_name)
                except MetaDataError as e:
                    errors.append('-1\t-1\t' + e.message)

            # If there are errors report them and return the error page
            if len(errors) > 0:
                log('Errors in metadata')
                cp.session['error_file'] = new_dir / ('errors_' + str(myMetaData.filename))
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
                log('Some warnings')
                cp.session['uploaded_files'] = [metadata_copy]
                # Write the errors to a file
                with open(new_dir / ('warnings_' + myMetaData.filename), 'w') as f:
                    f.write('\n'.join(warnings))

                # Get the html for the upload page
                uploaded_output = mmeds.load_html('warning', title='Warnings')

                for i, warning in enumerate(warnings):
                    uploaded_output = insert_warning(uploaded_output, 22 + i, warning)

                return uploaded_output
            else:
                # If there are no errors or warnings proceed to upload the data files
                log('No errors or warnings')
                cp.session['uploaded_files'] = [metadata_copy]
                page = mmeds.load_html('upload_data', title='Upload data', user=self.get_user())
                return page
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
            return page

    @cp.expose
    def process_data(self, reads, barcodes, public='off'):
        log('In process_data')
        cp.log('In process_data')
        try:
            # Create a unique dir for handling files uploaded by this user
            metadata_copy = cp.session['uploaded_files'].pop()

            # Set the User
            if public == 'on':
                username = 'public'
            else:
                username = self.get_user()

            # Start a process to handle loading the data
            p = Process(target=handle_data_upload,
                        args=(metadata_copy,
                              reads,
                              barcodes,
                              username,
                              cp.session['dir'],
                              self.testing))
            log('Starting upload process')
            cp.log('Starting upload process')
            p.start()

            # Get the html for the upload page
            page = mmeds.load_html('welcome',
                                   title='Welcome to Mmeds',
                                   user=self.get_user())
            html = '<h1> Your data is being uploaded, you will recieve an email when this finishes </h1>'
            page = insert_error(page, 22, html)
            log('Finish validate')
            return page
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
            return page

    ########################################
    #             Upload Pages             #
    ########################################

    @cp.expose
    def retry_upload(self):
        """ Retry the upload of data files. """
        log('In retry_upload')
        try:
            with open(HTML_DIR / 'upload.html') as f:
                page = f.read()
            page = page.format(user=self.get_user())
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        return page

    @cp.expose
    def modify_upload(self, myData, data_type, access_code):
        """ Modify the data of an existing upload. """
        log('In modify_upload')
        try:
            try:
                with Database('.', owner=self.get_user(), testing=testing) as db:
                    # Create a copy of the Data file
                    files, path = db.get_mongo_files(access_code=access_code)
                # Start a process to handle loading the data
                p = Process(target=handle_modify_data,
                            args=(access_code,
                                  myData,
                                  self.get_user(),
                                  data_type,
                                  self.testing))
                p.start()
            except MissingUploadError:
                with open(HTML_DIR / 'download_error.html') as f:
                    download_error = f.read()
                    return download_error.format(user=self.get_user())
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
        log('In convert_metadata')
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
    def upload_data(self):
        log('In upload_data')
        cp.log('In upload_data')
        try:
            # If there are no errors or warnings proceed to upload the data files
            page = mmeds.load_html('upload_data', title='Upload data', user=self.get_user())
            return page
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
            return page

    @cp.expose
    def upload_metadata(self, study_type):
        """ Page for uploading Qiime data """
        log('In upload_metadata')
        try:
            page = mmeds.load_html('upload_metadata',
                                   title='Upload Qiime',
                                   user=self.get_user(),
                                   version=study_type)
        except LoggedOutError:
            with open(HTML_DIR / 'index.html') as f:
                page = f.read()
        log('Exit upload')
        return page

    @cp.expose
    def query_page(self):
        """ Skip uploading a file. """
        log('In query_page')
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
