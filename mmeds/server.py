import os
import tempfile
import cherrypy as cp

from cherrypy.lib import static
from pathlib import Path
from subprocess import run
from copy import deepcopy
import atexit


import mmeds.secrets as sec
import mmeds.error as err

from mmeds.validate import validate_mapping_file
from mmeds.util import (load_html, insert_html, insert_error, insert_warning, log, MIxS_to_mmeds,
                        mmeds_to_MIxS, decorate_all_methods, catch_server_errors, create_local_copy)
from mmeds.config import UPLOADED_FP, HTML_DIR, USER_FILES, HTML_PAGES, DEFAULT_CONFIG, HTML_ARGS
from mmeds.authentication import (validate_password, check_username, check_password, check_privileges,
                                  add_user, reset_password, change_password)
from mmeds.database import Database
from mmeds.spawn import handle_modify_data

absDir = Path(os.getcwd())


def kill_watcher(monitor):
    """ A function to shutdown the Watcher instance when the server exits """
    monitor.terminate()
    while monitor.is_alive():
        log('Try to terminate')
        log('Try to kill')
        monitor.kill()


# Note: In all of the following classes, if a parameter is named in camel case instead of underscore
# (e.g. studyName vs. study_name) that incidates that the parameter is coming from an HTML forum

class MMEDSbase:
    """
    The base class inherited by all mmeds server classes.
    Contains no exposed webpages, only internal functionality used by mutliple pages.
    """

    def __init__(self, watcher, q, testing=False):
        self.db = None
        self.testing = bool(int(testing))
        self.monitor = watcher
        self.q = q
        # Set the server to kill the watcher process on exit
        atexit.register(kill_watcher, self.monitor)

    def exit(self):
        kill_watcher(self.monitor)
        cp.engine.exit()

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

        # Store the copy's location
        cp.session['uploaded_files'][cp.session['metadata_type']] = metadata_copy

        # Check the metadata file for errors
        errors, warnings, subjects = validate_mapping_file(metadata_copy,
                                                           cp.session['metadata_type'],
                                                           cp.session['subject_ids'],
                                                           cp.session['subject_type'])

        # The database for any issues with previous uploads for the subject metadata
        with Database('.', owner=self.get_user(), testing=self.testing) as db:
            try:
                if cp.session['metadata_type'] == 'subject':
                    warnings += db.check_repeated_subjects(subjects, cp.session['subject_type'])
                    cp.session['subject_ids'] = subjects
                elif cp.session['metadata_type'] == 'specimen':
                    errors += db.check_user_study_name(cp.session['study_name'])
                else:
                    raise err.MmedsError('Invalid metadata type')
            except err.MetaDataError as e:
                errors.append('-1\t-1\t' + e.message)
        return errors, warnings

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
        cp.log('handle_metadata_warnings, type: {}'.format(cp.session['metadata_type']))
        # Write the errors to a file
        with open(self.get_dir() / ('warnings_{}'.format(Path(metadata_copy).name)), 'w') as f:
            f.write('\n'.join(warnings))

        # Get the html for the upload page
        # Set the proceed button based on current metadata file
        if cp.session['metadata_type'] == 'subject':
            page = self.format_html('upload_metadata_warning', title='Warnings', next_page='../upload/retry_upload')
            cp.session['metadata_type'] = 'specimen'
        elif cp.session['metadata_type'] == 'specimen':
            page = self.format_html('upload_metadata_warning', title='Warnings', next_page='../upload/upload_data')

        # Add the warnings
        for i, warning in enumerate(warnings):
            page = insert_warning(page, 22 + i, warning)

        return page

    def load_data_files(self, **kwargs):
        """ Load the files passed that exist. """
        files = {}
        for key, value in kwargs.items():
            if value is not None:
                file_copy = create_local_copy(value.file, value.filename, self.get_dir())
                files[key] = file_copy
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

        # Named formatting arguments for web pages
        args = deepcopy(HTML_ARGS)

        args.update(kwargs)

        # If a user is logged in, load the side bar
        if header:
            template = HTML_PAGES['logged_in_template'].read_text()
            args['user'] = self.get_user()
            args['dir'] = self.get_dir()
        else:
            template = HTML_PAGES['logged_out_template'].read_text()
        body = path.read_text()

        args['body'] = body.format(**args)
        args['title'] = title

        # TODO: A hack to prevent the page displaying before the CSS loads
        # page_hider = '<head><div id="loadOverlay" style="background-color:#FFFFFF;\
        #     position:absolute; top:0px; left:0px; width:100%; height:100%; z-index:2000;"></div></head>\n'

        return template.format(**args)

    def add_process(self, ptype, process):
        """ Add an analysis process to the list of processes. """
        self.monitor.add_process(ptype, process)


@decorate_all_methods(catch_server_errors)
class MMEDSdownload(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)

    ########################################
    #            Download Pages            #
    ########################################

    @cp.expose
    def select_study(self):
        """ Allows authorized user accounts to access uploaded studies. """
        if check_privileges(self.get_user(), self.testing):
            page = self.format_html('download_select_study', title='Select Study')
            with Database(path='.', testing=self.testing) as db:
                studies = db.get_all_studies()
            for study in studies:
                page = insert_html(page, 24, '<option value="{}">{}</option>'.format(study.access_code,
                                                                                     study.study_name))
        else:
            page = self.format_html('welcome', title='Welcome to MMEDS')
            page = insert_error(page, 24, 'You do not have permissions to access uploaded studies.')
        return page

    @cp.expose
    def download_study(self, study_code):
        """ Display the information and files of a particular study. """
        with Database(path='.', testing=self.testing) as db:
            study = db.get_doc(study_code, check_owner=False)
            analyses = db.get_all_analyses_from_study(study_code)

        page = self.format_html('download_selected_study',
                                title='Study: {}'.format(study.study_name),
                                study=study.study_name,
                                date_created=study.created,
                                last_accessed=study.last_accessed,
                                doc_type=study.doc_type,
                                reads_type=study.reads_type,
                                barcodes_type=study.barcodes_type,
                                access_code=study.access_code,
                                owner=study.owner,
                                email=study.email,
                                path=study.path)

        for filename, filepath in study.files.items():
            page = insert_html(page, 34, '<option value="{}">{}</option>'.format(filepath, filename))

        for analysis in analyses:
            page = insert_html(page, 39 + len(study.files.keys()),
                               '<option value="{}">{}</option>'.format(analysis.access_code,
                                                                       analysis.name))
        return page

    @cp.expose
    def download_filepath(self, file_path):
        return static.serve_file(file_path, 'application/x-download',
                                 'attachment', os.path.basename(file_path))

    @cp.expose
    def select_analysis(self, access_code):
        """ Display the information and files of a particular study. """
        with Database(path='.', testing=self.testing) as db:
            analysis = db.get_doc(access_code, check_owner=False)

        page = self.format_html('download_selected_analysis',
                                title='Analysis: {}'.format(analysis.name),
                                name=analysis.name,
                                date_created=analysis.created,
                                last_accessed=analysis.last_accessed,
                                doc_type=analysis.doc_type,
                                reads_type=analysis.reads_type,
                                barcodes_type=analysis.barcodes_type,
                                study_code=analysis.study_code,
                                sub_analysis=analysis.sub_analysis,
                                access_code=analysis.access_code,
                                analysis_status=analysis.analysis_status,
                                owner=analysis.owner,
                                email=analysis.email,
                                path=analysis.path)

        for filename, file_path in analysis.files.items():
            if Path(file_path).exists():
                if '.' not in file_path:
                    if not Path(file_path + '.tar.gz').exists():
                        cmd = 'tar -czvf {} -C {} {}'.format(file_path + '.tar.gz',
                                                             Path(file_path).parent,
                                                             Path(file_path).name)
                        run(cmd.split(' '), check=True)
                    file_path += '.tar.gz'
                page = insert_html(page, 37, '<option value="{}">{}</option>'.format(file_path, filename))
        return page

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
        return static.serve_file(cp.session['download_files'][file_name], 'application/x-download',
                                 'attachment', Path(cp.session['download_files'][file_name]).name)


@decorate_all_methods(catch_server_errors)
class MMEDSupload(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)

    ########################################
    #             Upload Pages             #
    ########################################

    @cp.expose
    def retry_upload(self):
        """ Retry the upload of data files. """
        page = self.format_html('upload_metadata_file',
                                title='Upload Metadata',
                                metadata_type=cp.session['metadata_type'].capitalize())
        if cp.session['metadata_type'] == 'specimen':
            page = insert_html(page, 26, 'Subject table uploaded successfully')
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
        if cp.session['upload_type'] == 'qiime':
            if cp.session['dual_barcodes']:
                page = self.format_html('upload_data_files_dual', title='Upload Data')
            else:
                page = self.format_html('upload_data_files', title='Upload Data')
        elif cp.session['upload_type'] == 'sparcc':
            page = self.format_html('upload_otu_data', title='Upload Data')
        elif cp.session['upload_type'] == 'lefse':
            page = self.format_html('upload_lefse_data', title='Upload Data')
        return page

    @cp.expose
    def upload_page(self):
        """ Page for selecting upload type or modifying upload. """
        cp.log('Access upload page')
        page = self.format_html('upload_select_page', title='Upload Type')
        return page

    @cp.expose
    def upload_metadata(self, uploadType, subjectType, studyName):
        """ Page for uploading Qiime data """
        cp.session['study_name'] = studyName
        cp.session['metadata_type'] = 'subject'
        cp.session['subject_type'] = subjectType
        cp.session['upload_type'] = uploadType
        page = self.format_html('upload_metadata_file',
                                title='Upload Metadata',
                                metadata_type=cp.session['metadata_type'].capitalize(),
                                version=uploadType)
        return page

    @cp.expose
    def validate_metadata(self, myMetaData, barcodes_type, temporary=False):
        """ The page returned after a file is uploaded. """
        try:
            cp.log('in validate, current metadata {}'.format(cp.session['metadata_type']))
            # If the metadata is temporary don't perform validation
            if temporary:
                cp.session['metadata_temporary'] = True
                metadata_copy = create_local_copy(myMetaData.file, myMetaData.filename, self.get_dir())
                errors, warnings = [], []
            else:
                cp.session['metadata_temporary'] = False
                errors, warnings = self.run_validate(myMetaData)
            metadata_copy = cp.session['uploaded_files'][cp.session['metadata_type']]
            if barcodes_type == 'dual':
                cp.session['dual_barcodes'] = True
            else:
                cp.session['dual_barcodes'] = False

            # If there are errors report them and return the error page
            if errors:
                page = self.handle_metadata_errors(metadata_copy, errors, warnings)
            elif warnings:
                page = self.handle_metadata_warnings(metadata_copy, errors, warnings)
            else:
                # If there are no errors or warnings proceed to upload the data files
                log('No errors or warnings')
                # If it's the subject metadata file return the page for uploading the specimen metadata
                if cp.session['metadata_type'] == 'subject':
                    page = self.format_html('upload_metadata_file', title='Upload Metadata', metadata_type='Specimen')
                    page = insert_warning(page, 23, 'Subject table uploaded successfully')
                    cp.session['metadata_type'] = 'specimen'
                # Otherwise proceed to uploading data files
                elif cp.session['metadata_type'] == 'specimen':
                    # If it's the sspecimen metadata file, save the type of barcodes
                    # And return the page for uploading data files
                    page = self.upload_data()

        except err.MetaDataError as e:
            page = self.format_html('upload_metadata_file',
                                    title='Upload Metadata',
                                    metadata_type=cp.session['metadata_type'])
            page = insert_error(page, 22, e.message)
        return page

    @cp.expose
    def process_data(self, public=False, **kwargs):
        print(kwargs)
        cp.log('Public is {}'.format(public))

        # Create a unique dir for handling files uploaded by this user
        subject_metadata = Path(cp.session['uploaded_files']['subject'])
        specimen_metadata = Path(cp.session['uploaded_files']['specimen'])

        # Get the username
        username = self.get_user()

        # Unpack kwargs based on barcode type
        # Add the datafiles that exist as arguments
        if cp.session['upload_type'] == 'qiime':
            if cp.session['dual_barcodes']:
                # If have dual barcodes, don't have a reads_type in kwargs so must set it
                barcodes_type = 'dual_barcodes'
                datafiles = self.load_data_files(for_reads=kwargs['for_reads'],
                                                 rev_reads=kwargs['rev_reads'],
                                                 for_barcodes=kwargs['for_barcodes'],
                                                 rev_barcodes=kwargs['rev_barcodes'])
                reads_type = 'paired_end'
            else:
                barcodes_type = 'single_barcodes'
                datafiles = self.load_data_files(for_reads=kwargs['for_reads'],
                                                 rev_reads=kwargs['rev_reads'],
                                                 barcodes=kwargs['barcodes'])
                reads_type = kwargs['reads_type']
        elif cp.session['upload_type'] == 'sparcc':
            datafiles = self.load_data_files(otu_table=kwargs['otu_table'])
            reads_type = None
            barcodes_type = None
        elif cp.session['upload_type'] == 'lefse':
            datafiles = self.load_data_files(lefse_table=kwargs['lefse_table'])
            # Use reads_type variable to store if data file contins subclass and subjects
            if 'subclass' in kwargs.keys():
                reads_type = 'subclass'
                if 'subjects' in kwargs.keys():
                    reads_type = reads_type + '_subjects'
            elif 'subjects' in kwargs.keys():
                reads_type = 'subjects'
            else:
                reads_type = 'class_only'
            barcodes_type = None

        # Add the files to be uploaded to the queue for uploads
        # This will be handled by the Watcher class found in spawn.py
        self.q.put(('upload', cp.session['study_name'], subject_metadata, cp.session['subject_type'],
                    specimen_metadata, username, reads_type, barcodes_type, datafiles,
                    cp.session['metadata_temporary'], public))

        # Get the html for the upload page
        page = self.format_html('home')
        page = insert_warning(page, 23, 'Upload Initiated. You will recieve an email when this finishes')
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSauthentication(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)

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
            cp.session['uploaded_files'] = {}
            cp.session['subject_ids'] = None
            page = self.format_html('home', title='Welcome to Mmeds')
            log('Login Successful')
        except err.InvalidLoginError as e:
            page = self.format_html('login')
            page = insert_error(page, 14, e.message)
        return page

    @cp.expose
    def logout(self):
        """ Expires the session and returns to login page """
        cp.log('Logout user {}'.format(self.get_user()))
        cp.lib.sessions.expire()
        return self.format_html('login')

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
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)

    ######################################
    #              Analysis              #
    ######################################

    @cp.expose
    def run_analysis(self, access_code, analysis_method, config):
        """
        Run analysis on the specified study
        ----------------------------------------
        :access_code: The code that identifies the dataset to run the tool on
        :analysis_method: The tool and analysis to run on the chosen dataset
        """
        if '-' in analysis_method:
            tool_type = analysis_method.split('-')[0]
            analysis_type = analysis_method.split('-')[1]
        else:
            tool_type = analysis_method
            analysis_type = 'default'
        try:
            self.check_upload(access_code)
            print('config passed is {}'.format(config))
            if config.file is None:
                config_path = DEFAULT_CONFIG.read_text()
            elif isinstance(config, str):
                config_path = config
            else:
                config_path = create_local_copy(config.file, config.name)

            # -1 is the kill_stage (used when testing)
            self.q.put(('analysis', self.get_user(), access_code, tool_type, analysis_type, config_path, -1))
            page = self.format_html('welcome', title='Welcome to MMEDS')
            page = insert_warning(page, 22, 'Analysis started you will recieve an email shortly')
        except (err.InvalidConfigError, err.MissingUploadError, err.UploadInUseError) as e:
            page = self.format_html('analysis_page', title='Welcome to MMEDS')
            page = insert_error(page, 22, e.message)
        return page

    @cp.expose
    def view_corrections(self):
        """ Page containing the marked up metadata as an html file """
        log('In view_corrections')
        return open(self.get_dir() / (UPLOADED_FP + '.html'))

    @cp.expose
    def analysis_page(self):
        """ Page for running analysis of previous uploads. """
        page = self.format_html('analysis_select_tool', title='Select Analysis')
        return page

    @cp.expose
    def query_page(self):
        """ Load the page for executing Queries. """
        page = self.format_html('analysis_query', title='Execute Query')
        return page

    @cp.expose
    def execute_query(self, query):
        """ Execute the provided query and format the results as an html table """
        page = self.format_html('analysis_query')
        try:
            # Set the session to use the current user
            with Database(self.get_dir(), user=sec.SQL_USER_NAME, owner=self.get_user(), testing=self.testing) as db:
                data, header = db.execute(query)
                html_data = db.format_html(data, header)

            # Create a file with the results of the query
            query_file = self.get_dir() / 'query.tsv'
            if header is not None:
                data = [header] + list(data)
            with open(query_file, 'w') as f:
                f.write('\n'.join(list(map(lambda x: '\t'.join(list(map(str, x))), data))))
            cp.session['download_files']['query'] = query_file

            # Add the download button
            html = '<form action="../download/download_file" method="post">\n\
                    <button type="submit" name="file_name" value="query">Download Results</button>\n\
                    </form>'
            page = insert_html(page, 29, html_data + html)
        except (err.InvalidSQLError, err.TableAccessError) as e:
            page = insert_error(page, 29, e.message)
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSserver(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)
        self.download = MMEDSdownload(watcher, q, testing)
        self.analysis = MMEDSanalysis(watcher, q, testing)
        self.upload = MMEDSupload(watcher, q, testing)
        self.auth = MMEDSauthentication(watcher, q, testing)

    @cp.expose
    def index(self):
        """ Home page of the application """
        if cp.session.get('user'):
            page = self.format_html('home')
        else:
            page = self.format_html('login')
        return page
