import os
import tempfile
import cherrypy as cp

from cherrypy.lib import static
from pathlib import Path
from subprocess import run
from functools import wraps
from inspect import isfunction
from copy import deepcopy


import mmeds.secrets as sec
import mmeds.error as err
import mmeds.util as util

from mmeds.validate import validate_mapping_file
from mmeds.util import (insert_html, log, MIxS_to_mmeds, mmeds_to_MIxS, create_local_copy, SafeDict)
from mmeds.config import UPLOADED_FP, USER_FILES, HTML_PAGES, DEFAULT_CONFIG, HTML_ARGS, SERVER_PATH
from mmeds.authentication import (validate_password, check_username, check_password, check_privileges,
                                  add_user, reset_password, change_password)
from mmeds.database import Database
from mmeds.spawn import handle_modify_data
from mmeds.log import MMEDSLog

absDir = Path(os.getcwd())

logger = MMEDSLog('debug').logger


def catch_server_errors(page_method):
    """ Handles LoggedOutError, and HTTPErrors for all mmeds pages. """
    @wraps(page_method)
    def wrapper(*a, **kwargs):
        try:
            return page_method(*a, **kwargs)
        except err.LoggedOutError:
            body = HTML_PAGES['login'][0].read_text()
            args = deepcopy(HTML_ARGS)
            args['body'] = body.format(**args)
            return HTML_PAGES['logged_out_template'].read_text().format(**args)

        except KeyError as e:
            logger.error(e)
            return "There was an error, contact server admin with:\n {}".format(e)
    return wrapper


def decorate_all_methods(decorator):
    def apply_decorator(cls):
        for k, m in cls.__dict__.items():
            if isfunction(m):
                setattr(cls, k, decorator(m))
        return cls
    return apply_decorator


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

    def at_exit(self):
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
            raise err.MetaDataError('{} is not a valid filetype.'.format(file_extension))

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
        try:
            path, header = HTML_PAGES[page]

            # Handle any user alerts messages
            kwargs = util.format_alerts(kwargs)

            # Predefined arguments to format in
            args = SafeDict(HTML_ARGS)

            # Add the arguments included in this format call
            args.update(kwargs)

            # Add the mmeds stats
            args.update(util.load_mmeds_stats(self.testing))

            # If a user is logged in, load the side bar
            if header:
                template = HTML_PAGES['logged_in_template'].read_text()
                if args.get('user') is None:
                    args['user'] = self.get_user()
                    args['dir'] = self.get_dir()
            else:
                template = HTML_PAGES['logged_out_template'].read_text()

            # Load the body of the requested webpage
            body = path.read_text()

            # Insert the body into the outer template
            page = template.format_map(SafeDict({'body': body}))

            # Format all provided arguments
            page = page.format_map(args)

        # Log arguments if there is an issue
        except (ValueError, KeyError):
            cp.log('Args')
            cp.log('\n'.join([str(x) for x in kwargs.items()]))
            cp.log('=================================')
            cp.log(page)
            raise

        # Check there is nothing missing from the page
        if args.missed:
            raise err.FormatError(args.missed)

        return page

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
    def download_filepath(self, file_path):
        return static.serve_file(file_path, 'application/x-download',
                                 'attachment', os.path.basename(file_path))

    @cp.expose
    def download_file(self, file_name):
        return static.serve_file(cp.session['download_files'][file_name], 'application/x-download',
                                 'attachment', Path(cp.session['download_files'][file_name]).name)


@decorate_all_methods(catch_server_errors)
class MMEDSstudy(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)

    def format_html(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('study_selected') is None:
            kwargs['study_selected'] = 'w3-blue'
        return super().format_html(page, **kwargs)

    @cp.expose
    def select_study(self):
        """ Allows authorized user accounts to access uploaded studies. """
        study_html = ''' <tr class="w3-hover-blue">
            <th>
            <a href="{view_study_page}?access_code={access_code}"> {study_name} </a>
            </th>
            <th>{date_created}</th>
            <th>{num_analyses}</th>
        </tr> '''
        # If user has elevated privileges show them all uploaded studies
        if check_privileges(self.get_user(), self.testing):
            with Database(path='.', testing=self.testing) as db:
                studies = db.get_all_studies()
        # Otherwise only show studies they've uploaded
        else:
            with Database(path='.', testing=self.testing) as db:
                studies = db.get_all_user_studies(self.get_user())

        study_list = []
        for study in studies:
            study_list.append(study_html.format(study_name=study.study_name,
                                                view_study_page=SERVER_PATH + 'study/view_study',
                                                access_code=study.access_code,
                                                date_created=study.created,
                                                num_analyses=0))

        page = self.format_html('study_select_page',
                                title='Select Study',
                                user_studies='\n'.join(study_list),
                                public_studies="")

        return page

    @cp.expose
    def view_study(self, access_code):
        """ The page for viewing information on a particular study """
        with Database(path='.', testing=self.testing, owner=self.get_user()) as db:
            # Check the study belongs to the user only if the user doesn't have elevated privileges
            study = db.get_doc(access_code, not check_privileges(self.get_user(), self.testing))
            docs = db.get_docs(study_code=access_code)

        option_template = '<option value="{}">{}</option>'

        # Get analyses related to this study
        analyses = [option_template.format(doc.access_code, '{}-{} {}'.format(doc.tool_type,
                                                                              doc.analysis_type,
                                                                              doc.created.strftime("%Y-%m-%d")))
                    for doc in docs]

        # TODO pass study params as kwargs
        # Get files downloadable from this study
        study_files = [option_template.format(key, key.capitalize()) for key in study.files.keys()]

        for key, path in study.files.items():
            cp.session['download_files'][key] = path

        page = self.format_html('study_view_page',
                                title=study.study_name,
                                study_name=study.study_name,
                                date_created=study.created,
                                last_accessed=study.last_accessed,
                                reads_type=study.reads_type,
                                barcodes_type=study.barcodes_type,
                                access_code=study.access_code,
                                owner=study.owner,
                                email=study.email,
                                path=study.path,
                                study_analyses=analyses,
                                study_files=study_files)
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSupload(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)

    ########################################
    #             Upload Pages             #
    ########################################

    def format_html(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('upload_selected') is None:
            kwargs['upload_selected'] = 'w3-blue'

        # Handle what input forms should appear based on previous selections
        if cp.session.get('upload_type') == 'qiime':
            if cp.session.get('dual_barcodes'):
                kwargs['dual_barcodes'] = 'required'
                kwargs['select_barcodes'] = 'style="display:none"'
            else:
                kwargs['dual_barcodes'] = 'style="display:none"'
                kwargs['select_barcodes'] = ''
        # If it's not qiime (aka fastq) input then don't display the options
        else:
            kwargs['dual_barcodes'] = 'style="display:none"'
            kwargs['select_barcodes'] = 'style="display:none"'

        # Handle if the lefse input options should display when uploading a table
        if cp.session.get('upload_type') == 'lefse':
            kwargs['lefse_table'] = ''
            kwargs['table_type'] = 'Lefse'
        else:
            kwargs['lefse_table'] = 'style="display:none"'
            kwargs['table_type'] = 'OTU'
        kwargs['table_type_lower'] = kwargs['table_type'].lower()

        return super().format_html(page, **kwargs)

    @cp.expose
    def retry_upload(self):
        """ Retry the upload of data files. """
        logger.debug('upload/retry_upload')
        # Add the success message if applicable
        if cp.session['metadata_type'] == 'specimen':
            page = self.format_html('upload_metadata_file',
                                    title='Upload Metadata',
                                    success='Subject table uploaded successfully',
                                    metadata_type=cp.session['metadata_type'].capitalize())
        else:
            page = self.format_html('upload_metadata_file',
                                    title='Upload Metadata',
                                    metadata_type=cp.session['metadata_type'].capitalize())
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
            page = self.format_html('home', success='Upload modification successful')
        except err.MissingUploadError as e:
            page = self.format_html('upload_select_page', title='Upload Type', error=e.message)
        return page

    @cp.expose
    def upload_data(self):
        """ The page for uploading data files of any type"""

        # Only arrive here if there are no errors or warnings proceed to upload the data files
        alert = 'Specimen metadata uploaded successfully'

        # The case for handling uploads of fastq files
        if cp.session['upload_type'] == 'qiime':
            page = self.format_html('upload_data_files', title='Upload Data', success=alert)
        else:
            page = self.format_html('upload_otu_data', title='Upload Data', success=alert)
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

        # Add the success message if applicable
        if cp.session['metadata_type'] == 'specimen':
            page = self.format_html('upload_metadata_file',
                                    title='Upload Metadata',
                                    success='Subject table uploaded successfully',
                                    metadata_type=cp.session['metadata_type'].capitalize(),
                                    version=uploadType)
        else:
            page = self.format_html('upload_metadata_file',
                                    title='Upload Metadata',
                                    metadata_type=cp.session['metadata_type'].capitalize(),
                                    version=uploadType)
        return page

    @cp.expose
    def continue_metadata_upload(self):
        """ Like Upload metadata, but the continuation if there are warnings in a file """
        # Only arrive here if there are no errors or warnings proceed to upload the data files
        alert = '{} metadata uploaded successfully'.format(cp.session['metadata_type'].capitalize())

        # Move on to uploading data files
        if cp.session['metadata_type'] == 'specimen':
            # The case for handling uploads of fastq files
            if cp.session['upload_type'] == 'qiime':
                page = self.format_html('upload_data_files', title='Upload Data', success=alert)
            else:
                page = self.format_html('upload_otu_data', title='Upload Data', success=alert)
        # Move on to uploading specimen metadata
        else:
            page = self.format_html('upload_metadata_file',
                                    title='Upload Metadata',
                                    success='Subject table uploaded successfully',
                                    metadata_type=cp.session['metadata_type'].capitalize(),
                                    version=cp.session['upload_type'])
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
                cp.log('There are errors')
                # Write the errors to a file
                cp.session['download_files']['error_file'] =\
                    self.get_dir() / ('errors_{}'.format(Path(metadata_copy).name))

                with open(cp.session['download_files']['error_file'], 'w') as f:
                    f.write('\n'.join(errors + warnings))
                cp.log('Created error file at {}'.format(cp.session['download_files']['error_file']))

                if warnings:
                    page = self.format_html('upload_metadata_error',
                                            error=errors,
                                            warning=warnings,
                                            title='Errors')
                else:
                    page = self.format_html('upload_metadata_error',
                                            error=errors,
                                            title='Errors')
            elif warnings:
                cp.log('There are warnings')
                # Set the proceed button based on current metadata file
                if cp.session['metadata_type'] == 'subject':
                    page = self.format_html('upload_metadata_warning',
                                            title='Warnings',
                                            warning=warnings,
                                            next_page='{retry_upload_page}')
                    cp.session['metadata_type'] = 'specimen'
                elif cp.session['metadata_type'] == 'specimen':
                    page = self.format_html('upload_metadata_warning',
                                            title='Warnings',
                                            warning=warnings,
                                            next_page='{upload_data_page}')
            else:
                # If it's the subject metadata file return the page for uploading the specimen metadata
                if cp.session['metadata_type'] == 'subject':
                    page = self.format_html('upload_metadata_file',
                                            title='Upload Metadata',
                                            metadata_type='Specimen',
                                            success='Subject table uploaded successfully')
                    cp.session['metadata_type'] = 'specimen'
                    # Otherwise proceed to uploading data files
                elif cp.session['metadata_type'] == 'specimen':
                    # If it's the sspecimen metadata file, save the type of barcodes
                    # And return the page for uploading data files
                    page = self.upload_data()

        except err.MetaDataError as e:
            page = self.format_html('upload_metadata_file',
                                    title='Upload Metadata',
                                    error=e.message,
                                    metadata_type=cp.session['metadata_type'])
        return page

    @cp.expose
    def process_data(self, public=False, **kwargs):
        """ The page for loading data files into the database """
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

        return self.format_html('home', success='Upload Initiated. You will recieve an email when this finishes')


@decorate_all_methods(catch_server_errors)
class MMEDSauthentication(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)

    ########################################
    #           Account Pages              #
    ########################################

    def format_html(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('account_selected') is None:
            kwargs['account_selected'] = 'w3-text-blue'
        return super().format_html(page, **kwargs)

    @cp.expose
    def register_account(self):
        """ Return the page for signing up. """
        return self.format_html('auth_sign_up_page')

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
            page = self.format_html('login', success='Account created successfully!')
        except (err.InvalidPasswordErrors, err.InvalidUsernameError) as e:
            logger.error('error, invalid something.\n{}'.format(e.message))
            page = self.format_html('auth_sign_up_page', error=e.message)
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

        # Check the old password matches
        try:
            validate_password(self.get_user(), password0, testing=self.testing)
            # Check the two copies of the new password match
            check_password(password1, password2)
            change_password(self.get_user(), password1, testing=self.testing)
            page = self.format_html('auth_change_password', success='Your password was successfully changed.')
        except (err.InvalidLoginError, err.InvalidPasswordErrors) as e:
            page = self.format_html('auth_change_password', error=e.message.split(','))
        return page

    @cp.expose
    def password_recovery(self):
        return self.format_html('forgot_password')

    @cp.expose
    def submit_password_recovery(self, username, email):
        """ Page for reseting a user's password. """
        try:
            reset_password(username, email, testing=self.testing)
            page = self.format_html('login', success='A new password has been sent to your email.')
        except err.NoResultError:
            page = self.format_html('login', error='No account exists with the provided username and email.')
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSanalysis(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)

    ######################################
    #              Analysis              #
    ######################################

    def format_html(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('analysis_selected') is None:
            kwargs['analysis_selected'] = 'w3-blue'
        return super().format_html(page, **kwargs)

    @cp.expose
    def view_analysis(self, access_code):
        """ The page for viewing information on a particular analysis """
        with Database(path='.', testing=self.testing, owner=self.get_user()) as db:
            # Check the study belongs to the user only if the user doesn't have elevated privileges
            analysis = db.get_doc(access_code, not check_privileges(self.get_user(), self.testing))

        option_template = '<option value="{}">{}</option>'

        # Get files downloadable from this study
        analysis_files = [option_template.format(key, key.capitalize())
                          for key, path in analysis.files.items()
                          if Path(path).exists()]

        for key, path in analysis.files.items():
            cp.session['download_files'][key] = path

        page = self.format_html('analysis_view_page',
                                title=analysis.study_name,
                                study_name=analysis.study_name,
                                analysis_name='{}-{}'.format(analysis.tool_type, analysis.analysis_type),
                                date_created=analysis.created,
                                last_accessed=analysis.last_accessed,
                                reads_type=analysis.reads_type,
                                barcodes_type=analysis.barcodes_type,
                                access_code=analysis.access_code,
                                owner=analysis.owner,
                                email=analysis.email,
                                path=analysis.path,
                                tool_type=analysis.tool_type,
                                analysis_type=analysis.analysis_type,
                                analysis_status=analysis.analysis_status,
                                analysis_files=analysis_files)
        return page

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
            page = self.format_html('home', title='Welcome to MMEDS',
                                    success='Analysis started you will recieve an email shortly')
        except (err.InvalidConfigError, err.MissingUploadError, err.UploadInUseError) as e:
            page = self.format_html('analysis_page', title='Welcome to MMEDS', error=e.message)
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


@decorate_all_methods(catch_server_errors)
class MMEDSserver(MMEDSbase):
    def __init__(self, watcher, q, testing=False):
        super().__init__(watcher, q, testing)
        self.download = MMEDSdownload(watcher, q, testing)
        self.analysis = MMEDSanalysis(watcher, q, testing)
        self.upload = MMEDSupload(watcher, q, testing)
        self.auth = MMEDSauthentication(watcher, q, testing)
        self.study = MMEDSstudy(watcher, q, testing)

    def format_html(self, page, **kwargs):
        """
        Add the highlighting for this section of the website as well as other relevant arguments
        """
        if kwargs.get('home_selected') is None:
            kwargs['home_selected'] = 'w3-text-blue'
        return super().format_html(page, **kwargs)

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
            page = self.format_html('login', error=e.message)
        return page

    @cp.expose
    def index(self):
        """ Home page of the application """
        if cp.session.get('user'):
            page = self.format_html('home')
        else:
            page = self.format_html('login')
        return page
