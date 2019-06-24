import os
import tempfile
import cherrypy as cp
import mmeds.secrets as sec
import mmeds.error as err

from cherrypy.lib import static
from pathlib import Path
from subprocess import run
from multiprocessing import Process, Queue
from datetime import datetime


from mmeds.validate import validate_mapping_file
from mmeds.util import (generate_error_html, load_html, insert_html, insert_error, insert_warning, log, MIxS_to_mmeds,
                        mmeds_to_MIxS, decorate_all_methods, catch_server_errors, create_local_copy, write_processes,
                        read_processes)
from mmeds.config import UPLOADED_FP, HTML_DIR, USER_FILES, HTML_PAGES
from mmeds.authentication import (validate_password,
                                  check_username,
                                  check_password,
                                  add_user,
                                  reset_password,
                                  change_password)
from mmeds.database import Database
from mmeds.spawn import spawn_analysis, handle_data_upload, handle_modify_data, Watcher

absDir = Path(os.getcwd())


class MMEDSbase:
    """
    The base class inherited by all mmeds server classes.
    Contains no exposed webpages, only internal functionality used by mutliple pages.
    """

    def __init__(self, testing=False):
        self.db = None
        self.testing = bool(int(testing))
        self.q = Queue()
        self.monitor = Watcher(testing, self.q)
        self.monitor.start()

    def get_user(self):
        """
        Return the current user. Delete them from the
        user list if session data is unavailable.
        """
        try:
            return cp.session['user']
        except KeyError:
            raise err.LoggedOutError('No user logged in')

    def get_dir(self):
        """
        Return the current user. Delete them from the
        user list if session data is unavailable.
        """
        try:
            return cp.session['working_dir']
        except KeyError:
            raise err.LoggedOutError('No user logged in')

    def check_upload(self, access_code):
        """ Raise an error if the upload is currently in use. """
        log('check upload {}'.format(access_code))
        log(cp.session['processes'])
        log(cp.session['processes'].get(access_code))
        try:
            log(cp.session['processes'].get(access_code).exitcode)
        except AttributeError:
            pass
        if cp.session['processes'].get(access_code) is not None and\
                cp.session['processes'][access_code].exitcode is None:
            log('Upload {} in use'.format(access_code))
            raise err.UploadInUseError()

    def run_validate(self, myMetaData):
        """ Run validate_mapping_file and return the results """
        # Check the file that's uploaded
        valid_extensions = ['txt', 'csv', 'tsv']
        file_extension = myMetaData.filename.split('.')[-1]
        if file_extension not in valid_extensions:
            raise err.MetaDataError('Error: {} is not a valid filetype.'.format(file_extension))

        # Create a copy of the MetaData
        metadata_copy = create_local_copy(myMetaData.file, myMetaData.filename, self.get_dir())

        # Check the metadata file for errors
        errors, warnings, study_name, subjects = validate_mapping_file(metadata_copy)

        # The database for any issues with previous uploads
        with Database('.', owner=self.get_user(), testing=self.testing) as db:
            try:
                warnings += db.check_repeated_subjects(subjects)
                errors += db.check_user_study_name(study_name)
            except err.MetaDataError as e:
                errors.append('-1\t-1\t' + e.message)
        return metadata_copy, errors, warnings

    def handle_metadata_errors(self, metadata_copy, errors, warnings):
        """ Create the page to return when there are errors in the metadata """
        log('Errors in metadata')
        log('\n'.join(errors))
        cp.session['download_files']['error_file'] = self.get_dir() / ('errors_{}'.format(Path(metadata_copy).name))
        # Write the errors to a file
        with open(cp.session['download_files']['error_file'], 'w') as f:
            f.write('\n'.join(errors + warnings))

        uploaded_output = self.format_html('upload_metadata_error', title='Errors')
        uploaded_output = insert_error(
            uploaded_output, 7, '<h3>' + self.get_user() + '</h3>')
        for i, warning in enumerate(warnings):
            uploaded_output = insert_warning(uploaded_output, 22 + i, warning)
        for i, error in enumerate(errors):
            uploaded_output = insert_error(uploaded_output, 22 + i, error)

        return uploaded_output  # generate_error_html(metadata_copy, errors, warnings)

    def handle_metadata_warnings(self, metadata_copy, errors, warnings):
        """ Create the page to return when there are errors in the metadata """
        log('Some warnings')
        cp.session['uploaded_files'] = [metadata_copy]

        # Write the errors to a file
        with open(self.get_dir() / ('warnings_{}'.format(Path(metadata_copy).name)), 'w') as f:
            f.write('\n'.join(warnings))

        # Get the html for the upload page
        page = self.format_html('upload_metadata_warning', title='Warnings')

        for i, warning in enumerate(warnings):
            page = insert_warning(page, 22 + i, warning)
        return page

    def load_data_files(self, **kwargs):
        """ Load the files passed that exist. """
        files = []
        for key, value in kwargs.items():
            if value is not None:
                files.append((key, value.filename, value.file))
        return files

    def format_html(self, page, **kwargs):
        """
        Load the requested HTML page, adding the header and topbar
        if necessary as well as any formatting arguments.
        """
        path, header = HTML_PAGES[page]

        if page in ['welcome', 'index']:
            title = 'Welcome to MMEDS'
        else:
            title = 'MMEDS Analysis Server'

        args = {
            'title': title,
            'version': 'Unknown'
        }
        args.update(kwargs)
        if header:
            args['user'] = self.get_user()
            args['dir'] = self.get_dir()
            return_page = load_html(path, **args)
        else:
            return_page = path.read_text()
        return return_page

    def add_process(self, ptype, process):
        """ Add an analysis process to the list of processes. """
        self.monitor.add_process(ptype, process)

@decorate_all_methods(catch_server_errors)
class MMEDSdownload(MMEDSbase):
    def __init__(self, testing=False):
        super().__init__(testing)

    ########################################
    #            Download Pages            #
    ########################################

    @cp.expose
    def download_page(self, access_code):
        """ Loads the page with the links to download data and metadata. """
        try:
            self.check_upload(access_code)
            # Get the open file handler
            with Database(path='.', owner=self.get_user(), testing=self.testing) as db:
                files, path = db.get_mongo_files(access_code)

            page = self.format_html('download_select_file', title='Select Download')
            for k, f in sorted(files.items(), reverse=True):
                if f is not None and any(regex.match(k) for regex in USER_FILES):
                    page = insert_html(page, 24, '<option value="{}">{}</option>'.format(k, k))
            cp.session['download_access'] = access_code
        except (err.MissingUploadError, err.UploadInUseError) as e:
                page = self.format_html('welcome')
                page = insert_error(page, 22, e.message)
        return page

    @cp.expose
    def select_download(self, download):
        cp.log('User{} requests download {}'.format(self.get_user(), download))
        with Database('.', owner=self.get_user(), testing=self.testing) as db:
            files, path = db.get_mongo_files(cp.session['download_access'])
        file_path = str(Path(path) / files[download])
        if 'dir' in download:
            cmd = 'tar -czvf {} -C {} {}'.format(file_path + '.tar.gz',
                                                 Path(file_path).parent,
                                                 Path(file_path).name)
            run(cmd.split(' '), check=True)
            file_path += '.tar.gz'
        cp.log('Fetching {}'.format(file_path))

        return static.serve_file(file_path, 'application/x-download',
                                 'attachment', os.path.basename(file_path))

    @cp.expose
    def download_file(self, file_name):
        return static.serve_file(cp.session['error_file'], 'application/x-download',
                                 'attachment', os.path.basename(cp.session['download_files'][file_name]))


@decorate_all_methods(catch_server_errors)
class MMEDSupload(MMEDSbase):
    def __init__(self, testing=False):
        super().__init__(testing)

    ########################################
    #             Upload Pages             #
    ########################################

    @cp.expose
    def retry_upload(self):
        """ Retry the upload of data files. """
        page = self.format_html('upload_metadata')
        return page

    @cp.expose
    def modify_upload(self, myData, data_type, access_code):
        """ Modify the data of an existing upload. """
        log('In modify_upload')
        try:
            # Handle modifying the uploaded data
            handle_modify_data(access_code,
                               (myData.filename, myData.file),
                               self.get_user(),
                               data_type,
                               self.testing)
            # Get the html for the upload page
            page = self.format_html('welcome')
            page = insert_html(page, 22, 'Upload modification successful')
        except err.MissingUploadError as e:
            page = self.format_html('upload_select_page', title='Upload Type')
            page = insert_error(page, 22, e.message)
        return page

    @cp.expose
    def convert_metadata(self, convertTo, myMetaData, unitCol, skipRows):
        """
        Convert the uploaded MIxS metadata file to a mmeds metadata file and return it.
        """
        log('In convert_metadata')
        meta_copy = create_local_copy(myMetaData.file, myMetaData.filename, self.get_dir())
        # Try the conversion
        try:
            if convertTo == 'mmeds':
                file_path = self.get_dir() / 'mmeds_metadata.tsv'
                # If it is successful return the converted file
                MIxS_to_mmeds(meta_copy, file_path, skip_rows=skipRows, unit_column=unitCol)
            else:
                file_path = self.get_dir() / 'mixs_metadata.tsv'
                mmeds_to_MIxS(meta_copy, file_path, skip_rows=skipRows, unit_column=unitCol)
            page = static.serve_file(file_path, 'application/x-download',
                                     'attachment', os.path.basename(file_path))
        # If there is an issue with the provided unit column display an error
        except err.MetaDataError as e:
            page = self.format_html('welcome', title='Welcome to Mmeds')
            page = insert_error(page, 31, e.message)
        return page

    @cp.expose
    def upload_data(self):
        log('In upload_data')
        cp.log('In upload_data')
        # If there are no errors or warnings proceed to upload the data files
        page = self.format_html('upload_data_files', title='Upload Data')
        return page

    @cp.expose
    def upload_page(self):
        """ Page for selecting upload type or modifying upload. """
        cp.log('Access upload page')
        page = self.format_html('upload_select_page', title='Upload Type')
        return page

    @cp.expose
    def upload_metadata(self, study_type):
        """ Page for uploading Qiime data """
        page = self.format_html('upload_metadata_file', title='Upload Metadata', version=study_type)
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSauthentication(MMEDSbase):
    def __init__(self, testing=False):
        super().__init__(testing)

    ########################################
    #           Account Pages              #
    ########################################

    @cp.expose
    def sign_up_page(self):
        """ Return the page for signing up. """
        return self.format_html('auth_sign_up_page')

    @cp.expose
    def login(self, username, password):
        """
        Opens the page to upload files if the user has been authenticated.
        Otherwise returns to the login page with an error message.
        """
        cp.log('Login attempt for user: {}'.format(username))
        try:
            validate_password(username, password, testing=self.testing)
            cp.session['user'] = username
            cp.session['temp_dir'] = tempfile.TemporaryDirectory()
            cp.session['working_dir'] = Path(cp.session['temp_dir'].name)
            cp.session['processes'] = {}
            cp.session['download_files'] = {}
            page = self.format_html('welcome', title='Welcome to Mmeds', user=self.get_user())
            log('Login Successful')
        except err.InvalidLoginError as e:
            page = self.format_html('index')
            page = insert_error(page, 14, e.message)
            log(e)
            log(e.message)
        return page

    @cp.expose
    def logout(self):
        """ Expires the session and returns to login page """
        cp.log('Logout user {}'.format(self.get_user()))
        cp.lib.sessions.expire()
        return open(HTML_DIR / 'index.html')

    @cp.expose
    def sign_up(self, username, password1, password2, email):
        """
        Perform the actions necessary to sign up a new user.
        """

        try:
            check_password(password1, password2)
            check_username(username, testing=self.testing)
            add_user(username, password1, email, testing=self.testing)
            page = self.format_html('index')
        except (err.InvalidPasswordErrors, err.InvalidUsernameError) as e:
            page = self.format_html('auth_sign_up_page')
            for message in e.message.split(','):
                page = insert_error(page, 25, message)
        return page

    @cp.expose
    def input_password(self):
        """ Load page for changing the user's password """
        page = self.format_html('auth_change_password', title='Change Password')
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
        page = self.format_html('auth_change_password', title='Change Password')

        # Check the old password matches
        try:
            validate_password(self.get_user(), password0, testing=self.testing)
            # Check the two copies of the new password match
            check_password(password1, password2)
            change_password(self.get_user(), password1, testing=self.testing)
            page = insert_html(page, 9, 'Your password was successfully changed.')
        except (err.InvalidLoginError, err.InvalidPasswordErrors) as e:
            for message in e.message.split(','):
                page = insert_error(page, 9, message)
        return page

    @cp.expose
    def reset_code(self, study_name, study_email):
        """ Skip uploading a file. """
        # Get the open file handler
        with Database(self.get_dir(), owner=self.get_user(), testing=self.testing) as db:
            try:
                db.reset_access_code(study_name, study_email)
                page = self.format_html('welcome')
                page = insert_html(page, 14, 'Upload Successful')
            except err.MissingUploadError:
                page = self.format_html('welcome')
                page = insert_error(page, 14, 'There was an error during the upload')
        return page

    @cp.expose
    def password_recovery(self, username, email):
        """ Page for reseting a user's password. """
        try:
            page = self.format_html('index')
            reset_password(username, email, testing=self.testing)
            page = insert_html(page, 14, 'A new password has been sent to your email.')
        except err.NoResultError:
            page = insert_error(
                page, 14, 'No account exists with the provided username and email.')
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSanalysis(MMEDSbase):
    def __init__(self, testing=False):
        super().__init__(testing)

    ######################################
    #              Analysis              #
    ######################################

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
            self.check_upload(access_code)
            p = spawn_analysis(tool, self.get_user(), access_code, config, self.testing)
            self.add_process('analysis', p.doc)
            cp.log('Valid config file')
            page = self.format_html('welcome', title='Welcome to MMEDS')
        except (err.InvalidConfigError, err.MissingUploadError, err.UploadInUseError) as e:
            page = self.format_html('welcome', title='Welcome to MMEDS')
            page = insert_error(page, 22, e.message)
        return page

    @cp.expose
    def view_corrections(self):
        """ Page containing the marked up metadata as an html file """
        log('In view_corrections')
        return open(self.get_dir() / (UPLOADED_FP + '.html'))

    @cp.expose
    def validate_metadata(self, myMetaData):
        """ The page returned after a file is uploaded. """
        log('In validate_metadata')
        try:
            metadata_copy, errors, warnings = self.run_validate(myMetaData)

            # If there are errors report them and return the error page
            if errors:
                page = self.handle_metadata_errors(metadata_copy, errors, warnings)
            elif warnings:
                page = self.handle_metadata_warnings(metadata_copy, errors, warnings)
            else:
                # If there are no errors or warnings proceed to upload the data files
                log('No errors or warnings')
                cp.session['uploaded_files'] = [metadata_copy]
                page = self.format_html('upload_data_files', title='Upload Data')
        except err.MetaDataError as e:
            page = self.format_html('upload_metadata_file', title='Upload Metadata')
            page = insert_error(page, 22, e.message)
        return page

    @cp.expose
    def process_data(self, for_reads, rev_reads, barcodes, reads_type, public='off'):
        # Create a unique dir for handling files uploaded by this user
        metadata = Path(cp.session['uploaded_files'].pop())

        # Set the User
        if public == 'on':
            username = 'public'
        else:
            username = self.get_user()

        # Add the datafiles that exist as arguments
        datafiles = self.load_data_files(for_reads=for_reads, rev_reads=rev_reads, barcodes=barcodes)

        # Start a process to handle loading the data
        p = Process(target=handle_data_upload,
                    args=(metadata, username, reads_type, self.testing,
                          # Unpack the list so the files are taken as a tuple
                          *datafiles))
        cp.log('Starting upload process')
        p.start()

        # Get the html for the upload page
        page = self.format_html('welcome', title='Welcome to MMEDS')
        html = '<h1> Your data is being uploaded, you will recieve an email when this finishes </h1>'
        page = insert_error(page, 22, html)
        return page

    @cp.expose
    def analysis_page(self):
        """ Page for running analysis of previous uploads. """
        page = self.format_html('analysis_select_tool', title='Select Analysis')
        return page

    @cp.expose
    def query_page(self):
        """ Skip uploading a file. """
        page = self.format_html('welcome')
        return page

    @cp.expose
    def query(self, query):
        # Set the session to use the current user
        username = self.get_user()
        with Database(self.get_dir(), user=sec.SQL_DATABASE_USER, owner=username, testing=self.testing) as db:
            data, header = db.execute(query)
            html_data = db.format(data, header)
            page = self.format_html('welcome')

        cp.session['download_files']['query'] = self.get_dir() / 'query.tsv'

        html = '<form action="download_query" method="post">\n\
                <button type="submit">Download Results</button>\n\
                </form>'
        page = insert_html(page, 10, html)
        page = insert_error(page, 10, html_data)
        if header is not None:
            data = [header] + list(data)
        with open(self.get_dir() / cp.session['query'], 'w') as f:
            f.write('\n'.join(list(map(lambda x: '\t'.join(list(map(str, x))), data))))
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSserver(MMEDSbase):
    def __init__(self, testing=False):
        super().__init__(testing)
        self.download = MMEDSdownload(testing)
        self.analysis = MMEDSanalysis(testing)
        self.upload = MMEDSupload(testing)
        self.auth = MMEDSauthentication(testing)

    @cp.expose
    def index(self):
        """ Home page of the application """
        if cp.session.get('user'):
            page = self.format_html('welcome', title='Welcome to MMEDS')
            self.add_process('test', 'User {} is logged in. The time is {}'.format(cp.session.get('user'),
                                                                                   datetime.now()))
        else:
            page = self.format_html('index')
            self.add_process('test', 'time is {}'.format(datetime.now()))
        return page
