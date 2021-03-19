import os
import cherrypy as cp
import getpass

from cherrypy.lib import static
from pathlib import Path
from functools import wraps
from inspect import isfunction
from copy import deepcopy

import mmeds.error as err
import mmeds.util as util
import mmeds.config as fig
import mmeds.formatter as fmt

from mmeds.validate import Validator, valid_file
from mmeds.util import (create_local_copy, SafeDict, load_mmeds_stats)
from mmeds.config import UPLOADED_FP, HTML_PAGES, HTML_ARGS, SERVER_PATH
from mmeds.authentication import (validate_password, check_username, check_password, check_privileges,
                                  add_user, reset_password, change_password)
from mmeds.database.database import Database
from mmeds.spawn import handle_modify_data, Watcher
from mmeds.logging import Logger

absDir = Path(os.getcwd())


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
    return wrapper


def decorate_all_methods(decorator):
    def apply_decorator(cls):
        for k, m in cls.__dict__.items():
            if isfunction(m):
                setattr(cls, k, decorator(m))
        return cls
    return apply_decorator


# Note: In all of the following classes, if a parameter is named in camel case instead of underscore
# (e.g. studyName vs. study_name) that incidates that the parameter is coming from an HTML form
# Update 2021-03-08: This is not as consistant as it should be

class MMEDSbase:
    """
    The base class inherited by all mmeds server classes.
    Contains no exposed webpages, only internal functionality used by mutliple pages.
    """

    def __init__(self):
        self.db = None
        self.testing = fig.TESTING
        self.monitor = Watcher()
        cp.log("{} Connecting to monitor".format(id(self)))
        self.monitor.connect()
        cp.log("{} Connected to monitor".format(id(self)))
        self.q = self.monitor.get_queue()
        cp.log("{} Got Queue".format(id(self)))

    def get_user(self):
        """
        Return the current user. Delete them from the
        user list if session data is unavailable.
        """
        try:
            return cp.session['user']
        except KeyError:
            cp.log('Get user failed')
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

    def get_privilege(self):
        try:
            privilege = cp.session['privilege']
        except KeyError:
            privilege = check_privileges(self.get_user(), self.testing)
            cp.session['privilege'] = privilege
        return privilege

    def check_upload(self, access_code):
        """ Raise an error if the upload does not exist or is currently in use. """
        try:
            cp.log(cp.session['processes'].get(access_code).exitcode)
        except AttributeError:
            pass
        if cp.session['processes'].get(access_code) is not None and\
                cp.session['processes'][access_code].exitcode is None:
            cp.log('Upload {} in use'.format(access_code))
            raise err.UploadInUseError()

        # Check that the upload does exist for the given user
        with Database(path='.', testing=self.testing, owner=self.get_user()) as db:
            db.check_upload(access_code)
            files, path = db.get_mongo_files(access_code)
        return files

    def load_webpage(self, page, **kwargs):
        """
        Load the requested HTML page, adding the header and topbar
        if necessary as well as any formatting arguments.
        """
        cp.log("Loading webpage")
        try:
            path, header = HTML_PAGES[page]

            # Handle any user alerts messages
            kwargs = util.format_alerts(kwargs)

            # Predefined arguments to format in
            args = SafeDict(HTML_ARGS)

            # Add the arguments included in this format call
            args.update(kwargs)

            # Add the mmeds stats
            args.update(load_mmeds_stats(self.testing))

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
            cp.log("Finished loading arguments for web page")

        # Log arguments if there is an issue
        except (ValueError, KeyError):
            cp.log('Exception, arguments not found')
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
        cp.log(f"Adding analysis process {process}")
        self.monitor.add_process(ptype, process)


@decorate_all_methods(catch_server_errors)
class MMEDSdownload(MMEDSbase):
    def __init__(self):
        super().__init__()

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

    @cp.expose
    def download_multiple_ids(self, studyName, idType):
        """ Generate a file containing the requested IDs and return it for download """
        with Database(path=self.get_dir(), testing=self.testing, owner=self.get_user()) as db:
            id_file = db.create_ids_file(studyName, idType)

        return static.serve_file(id_file, 'application/x-download', 'attachment', id_file.name)


@decorate_all_methods(catch_server_errors)
class MMEDSstudy(MMEDSbase):
    def __init__(self):
        super().__init__()

    def load_webpage(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('study_selected') is None:
            kwargs['study_selected'] = 'w3-blue'
        return super().load_webpage(page, **kwargs)

    @cp.expose
    def select_study(self):
        """ Allows authorized user accounts to access uploaded studies. """
        cp.log("In select study")
        # TODO Convert to a clickable table from formatter
        study_html = ''' <tr class="w3-hover-blue">
            <td>
            <a href="{view_study_page}?access_code={access_code}"> {study_name} </a>
            </td>
            <td>{date_created}</td>
            <td>{num_analyses}</td>
        </tr> '''
        # If user has elevated privileges show them all uploaded studies
        if check_privileges(self.get_user(), self.testing):
            with Database(path='.', testing=self.testing) as db:
                studies = db.get_all_studies()
        # Otherwise only show studies they've uploaded
        else:
            with Database(path='.', testing=self.testing) as db:
                studies = db.get_all_user_studies(self.get_user())
        cp.log("Found {} studies".format(len(studies)))

        study_list = []
        for study in studies:
            study_list.append(study_html.format(study_name=study.study_name,
                                                view_study_page=SERVER_PATH + 'study/view_study',
                                                access_code=study.access_code,
                                                date_created=study.created,
                                                num_analyses=0))

        cp.log("Build out study list")
        page = self.load_webpage('study_select_page',
                                 title='Select Study',
                                 user_studies='\n'.join(study_list),
                                 public_studies="")

        cp.log("Built out page")
        return page

    @cp.expose
    def view_study(self, access_code):
        """ The page for viewing information on a particular study """
        try:
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

            page = self.load_webpage('study_view_page',
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
        except err.MissingUploadError:
            Logger.error(err.MissingUploadError().message)
            page = self.load_webpage('home', error=err.MissingUploadError().message, title='Welcome to Mmeds')

        return page


@decorate_all_methods(catch_server_errors)
class MMEDSupload(MMEDSbase):
    def __init__(self):
        super().__init__()
    ########################################
    #         Upload Functionality         #
    ########################################

    def load_webpage(self, page, **kwargs):
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

        return super().load_webpage(page, **kwargs)

    def run_validate(self, myMetaData):
        """ Run validate_mapping_file and return the results """
        cp.log('In run validate')
        errors = []
        warnings = []
        # Check the file that's uploaded
        valid_extensions = ['txt', 'csv', 'tsv']
        file_extension = myMetaData.filename.split('.')[-1]
        if file_extension not in valid_extensions:
            raise err.MetaDataError('{} is not a valid filetype.'.format(file_extension))

        # Create a copy of the MetaData
        metadata_copy = create_local_copy(myMetaData.file, myMetaData.filename, self.get_dir())

        # Store the copy's location
        cp.session['uploaded_files'][cp.session['metadata_type']] = metadata_copy

        cp.log('before validator creation')
        valid = Validator(metadata_copy,
                          cp.session['study_name'],
                          cp.session['metadata_type'],
                          cp.session['subject_ids'],
                          cp.session['subject_type'])
        cp.log('before validator run')

        # Check the metadata file for errors
        errors, warnings, subjects = valid.run()

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

    def handle_errors_warnings(self, metadata_copy, errors, warnings):
        """ Handle loading different pages depending if there are metadata errors, warnings, or neither """
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
                page = self.load_webpage('upload_metadata_error',
                                         error=errors,
                                         warning=warnings,
                                         title='Errors')
            else:
                page = self.load_webpage('upload_metadata_error',
                                         error=errors,
                                         title='Errors')
        elif warnings:
            cp.log('There are warnings')
            # Set the proceed button based on current metadata file
            if cp.session['metadata_type'] == 'subject':
                page = self.load_webpage('upload_metadata_warning',
                                         title='Warnings',
                                         warning=warnings,
                                         next_page='{retry_upload_page}')
            elif cp.session['metadata_type'] == 'specimen':
                page = self.load_webpage('upload_metadata_warning',
                                         title='Warnings',
                                         warning=warnings,
                                         next_page='{upload_data_page}')
        else:
            # If it's the subject metadata file return the page for uploading the specimen metadata
            if cp.session['metadata_type'] == 'subject':
                page = self.load_webpage('upload_metadata_file',
                                         title='Upload Metadata',
                                         metadata_type='Specimen',
                                         success='Subject table uploaded successfully')
                cp.session['metadata_type'] = 'specimen'
                # Otherwise proceed to uploading data files
            elif cp.session['metadata_type'] == 'specimen':
                # If it's the sspecimen metadata file, save the type of barcodes
                # And return the page for uploading data files
                page = self.upload_data()
        return page

    ########################################
    #             Upload Pages             #
    ########################################

    @cp.expose
    def retry_upload(self):
        """ Retry the upload of data files. """
        cp.log('upload/retry_upload')
        # Add the success message if applicable
        if cp.session['metadata_type'] == 'subject':
            page = self.load_webpage('upload_metadata_file',
                                     title='Upload Metadata',
                                     success='Subject table uploaded successfully',
                                     metadata_type=cp.session['metadata_type'].capitalize())
        else:
            page = self.load_webpage('upload_metadata_file',
                                     title='Upload Metadata',
                                     metadata_type=cp.session['metadata_type'].capitalize())
        return page

    @cp.expose
    def modify_upload(self, myData, data_type, access_code):
        """ Modify the data of an existing upload. """
        cp.log('In modify_upload')
        try:
            # Handle modifying the uploaded data
            handle_modify_data(access_code,
                               (myData.filename, myData.file),
                               self.get_user(),
                               data_type,
                               self.testing)
            # Get the html for the upload page
            page = self.load_webpage('home', success='Upload modification successful')
        except err.MissingUploadError as e:
            page = self.load_webpage('upload_select_page', title='Upload Type', error=e.message)
        return page

    @cp.expose
    def upload_data(self):
        """ The page for uploading data files of any type"""

        # Only arrive here if there are no errors or warnings proceed to upload the data files
        alert = 'Specimen metadata uploaded successfully'

        # The case for handling uploads of fastq files
        if cp.session['upload_type'] == 'qiime':
            page = self.load_webpage('upload_data_files', title='Upload Data', success=alert)
        else:
            page = self.load_webpage('upload_otu_data', title='Upload Data', success=alert)
        return page

    @cp.expose
    def upload_page(self):
        """ Page for selecting upload type or modifying upload. """
        cp.log('Access upload page')
        page = self.load_webpage('upload_select_page', title='Upload Type')
        return page

    @cp.expose
    def upload_metadata(self, uploadType, subjectType, studyName):
        """ Page for uploading Qiime data """
        try:
            cp.session['study_name'] = studyName
            cp.session['metadata_type'] = 'subject'
            cp.session['subject_type'] = subjectType
            cp.session['upload_type'] = uploadType

            with Database(path='.', testing=self.testing, owner=self.get_user()) as db:
                db.check_study_name(studyName)

            # Add the success message if applicable
            if cp.session['metadata_type'] == 'specimen':
                page = self.load_webpage('upload_metadata_file',
                                         title='Upload Metadata',
                                         success='Subject table uploaded successfully',
                                         metadata_type=cp.session['metadata_type'].capitalize(),
                                         version=uploadType)
            else:
                page = self.load_webpage('upload_metadata_file',
                                         title='Upload Metadata',
                                         metadata_type=cp.session['metadata_type'].capitalize(),
                                         version=uploadType)
        except(err.StudyNameError) as e:
            page = self.load_webpage('upload_select_page', title='Upload Type', error=e.message)
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
                page = self.load_webpage('upload_data_files', title='Upload Data', success=alert)
            else:
                page = self.load_webpage('upload_otu_data', title='Upload Data', success=alert)
        # Move on to uploading specimen metadata
        else:
            cp.session['metadata_type'] = 'specimen'
            page = self.load_webpage('upload_metadata_file',
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

            page = self.handle_errors_warnings(metadata_copy, errors, warnings)

        except err.MetaDataError as e:
            page = self.load_webpage('upload_metadata_file',
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

        cp.log("Server putting upload in queue {}".format(id(self.q)))
        # Add the files to be uploaded to the queue for uploads
        # This will be handled by the Watcher class found in spawn.py
        self.q.put(('upload', cp.session['study_name'], subject_metadata, cp.session['subject_type'],
                    specimen_metadata, self.get_user(), reads_type, barcodes_type, datafiles,
                    cp.session['metadata_temporary'], public))

        return self.load_webpage('home', success='Upload Initiated. You will recieve an email when this finishes')

    @cp.expose
    def generate_multiple_ids(self, accessCode, idType, dataFile):
        """ Takes a file specifying the Aliquots to generate IDs for and passes it to the watcher """
        success = ''
        error = ''
        # Ensure that the access code is valid for a particular user
        try:
            self.check_upload(accessCode)
        except err.MissingUploadError as e:
            error = e.message
        else:
            data_file = self.load_data_files(idFile=dataFile)

            if valid_file(data_file['idFile'], idType):

                # Pass it to the watcher
                self.q.put(('upload-ids', self.get_user(), accessCode, data_file['idFile'], idType))
                success = f'{idType.capitalize()} ID Generation Initiated.' +\
                    'You will recieve an email when the ID generation finishes'
            else:
                error = 'There was an issue with your ID file. Please check the example.'
        return self.load_webpage('home', success=success, error=error)

    @cp.expose
    def upload_multiple_ids(self, accessCode, idType, dataFile):
        pass


@decorate_all_methods(catch_server_errors)
class MMEDSauthentication(MMEDSbase):
    def __init__(self):
        super().__init__()

    ########################################
    #           Account Pages              #
    ########################################

    def load_webpage(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('account_selected') is None:
            kwargs['account_selected'] = 'w3-text-blue'
        return super().load_webpage(page, **kwargs)

    @cp.expose
    def register_account(self):
        """ Return the page for signing up. """
        return self.load_webpage('auth_sign_up_page')

    @cp.expose
    def logout(self):
        """ Expires the session and returns to login page """
        cp.log('Logout user {}'.format(self.get_user()))
        cp.lib.sessions.expire()
        return self.load_webpage('login')

    @cp.expose
    def sign_up(self, username, password1, password2, email):
        """
        Perform the actions necessary to sign up a new user.
        """
        try:
            check_password(password1, password2)
            check_username(username, testing=self.testing)
            add_user(username, password1, email, testing=self.testing)
            page = self.load_webpage('login', success='Account created successfully!')
        except (err.InvalidPasswordErrors, err.InvalidUsernameError) as e:
            cp.log('error, invalid something.\n{}'.format(e.message))
            page = self.load_webpage('auth_sign_up_page', error=e.message)
        return page

    @cp.expose
    def input_password(self):
        """ Load page for changing the user's password """
        page = self.load_webpage('auth_change_password', title='Change Password')
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
            cp.lib.sessions.expire()
            validate_password(self.get_user(), password0, testing=self.testing)
            # Check the two copies of the new password match
            check_password(password1, password2)
            change_password(self.get_user(), password1, testing=self.testing)
            page = self.load_webpage('auth_change_password', success='Your password was successfully changed.')
        except (err.InvalidLoginError, err.InvalidPasswordErrors) as e:
            page = self.load_webpage('auth_change_password', error=e.message)
        return page

    @cp.expose
    def password_recovery(self):
        return self.load_webpage('forgot_password')

    @cp.expose
    def submit_password_recovery(self, username, email):
        """ Page for reseting a user's password. """
        try:
            reset_password(username, email, testing=self.testing)
            page = self.load_webpage('login', success='A new password has been sent to your email.')
        except err.NoResultError:
            page = self.load_webpage('login', error='No account exists with the provided username and email.')
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSanalysis(MMEDSbase):
    def __init__(self):
        super().__init__()

    ######################################
    #              Analysis              #
    ######################################

    def load_webpage(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('analysis_selected') is None:
            kwargs['analysis_selected'] = 'w3-blue'
        return super().load_webpage(page, **kwargs)

    @cp.expose
    def view_analysis(self, access_code):
        """ The page for viewing information on a particular analysis """

        cp.log("viewing analysis with code: {}".format(access_code))
        with Database(path='.', testing=self.testing, owner=self.get_user()) as db:
            # Check the study belongs to the user only if the user doesn't have elevated privileges
            analysis = db.get_doc(access_code, not self.get_privilege())

        option_template = '<option value="{}">{}</option>'

        # Get files downloadable from this study
        analysis_files = [option_template.format(key, key.capitalize())
                          for key, path in analysis.files.items()
                          if Path(path).exists()]

        # Get analyses performed on this study
        for key, path in analysis.files.items():
            if key == 'summary':
                path = path + '.zip'
            cp.session['download_files'][key] = path

        # Check that a zip of the analysis exists for download
        # If not (e.g. if the analysis failed part way through
        # do not display the button to download all files
        download_all_display = ''
        if Path(analysis.path + '.zip').exists():
            cp.session['download_files']['all'] = analysis.path + '.zip'
        else:
            download_all_display = 'display:none'

        page = self.load_webpage('analysis_view_page',
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
                                 download_all_display=download_all_display,
                                 analysis_type=analysis.analysis_type,
                                 analysis_status=analysis.analysis_status,
                                 analysis_files=analysis_files)
        return page

    @cp.expose
    def run_analysis(self, access_code, analysis_method, config, runOnNode=None):
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
            # The run on node option shouldn't appear for users without
            # elevated privileges but they could get around that by editting
            # the page html directly
            cp.log(f"runOnNode is ${runOnNode}")
            if runOnNode and not check_privileges(self.get_user(), self.testing):
                raise err.PrivilegeError('Only users with elevated privileges may run analysis directly')

            # Check that the requested upload exists
            # Getting the files to check the config options match the provided metadata
            files = self.check_upload(access_code)

            if isinstance(config, str):
                config_path = config
            elif config.file is None:
                config_path = ''
            else:
                config_path = create_local_copy(config.file, config.name, self.get_dir())

            # Check that the config file is valid
            util.load_config(config_path, files['metadata'])

            # -1 is the kill_stage (used when testing)
            self.q.put(('analysis', self.get_user(), access_code, tool_type,
                        analysis_type, config_path, -1, runOnNode))
            page = self.load_webpage('home', title='Welcome to MMEDS',
                                     success='Analysis started you will recieve an email shortly')
        except (err.InvalidConfigError, err.MissingUploadError,
                err.UploadInUseError, err.PrivilegeError) as e:
            page = self.load_webpage('analysis_select_tool', title='Select Analysis', error=e.message)
        return page

    @cp.expose
    def view_corrections(self):
        """ Page containing the marked up metadata as an html file """
        cp.log('In view_corrections')
        return open(self.get_dir() / (UPLOADED_FP + '.html'))

    @cp.expose
    def analysis_page(self):
        """ Page for running analysis of previous uploads. """
        # Add unhide any privileged options
        if check_privileges(self.get_user(), self.testing):
            page = self.load_webpage('analysis_select_tool', title='Select Analysis', privilege='')
        else:
            page = self.load_webpage('analysis_select_tool', title='Select Analysis')
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSquery(MMEDSbase):
    def __init__(self):
        super().__init__()

    def load_webpage(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('query_selected') is None:
            kwargs['query_selected'] = 'w3-blue'
        return super().load_webpage(page, **kwargs)

    @cp.expose
    def query_select(self):
        study_html = ''' <tr class="w3-hover-blue">
            <th>
            <a href="{select_specimen_page}?access_code={access_code}"> {study_name} </a>
            </th>
            <th>{date_created}</th>
        </tr> '''

        id_study_html = '<option value="{study_name}">{study_name}</option>'

        with Database(testing=self.testing) as db:
            studies = db.get_all_user_studies(self.get_user())

        study_list = []
        id_study_list = []
        for study in studies:
            study_list.append(study_html.format(study_name=study.study_name,
                                                select_specimen_page=SERVER_PATH + 'query/select_specimen',
                                                access_code=study.access_code,
                                                date_created=study.created,
                                                ))
            id_study_list.append(id_study_html.format(study_name=study.study_name))

        page = self.load_webpage('query_select_page',
                                 title='Select Study',
                                 user_studies='\n'.join(study_list),
                                 id_user_studies='\n'.join(id_study_list)
                                 )

        return page

    @cp.expose
    def execute_query(self, query):
        """ Execute the provided query and format the results as an html table """
        try:
            # Set the session to use the current user
            with Database(testing=self.testing) as db:
                data, header = db.execute(query)
                html_data = db.build_html_table(header, data)

            # Create a file with the results of the query
            query_file = self.get_dir() / 'query.tsv'
            if header is not None:
                data = [header] + list(data)
            with open(query_file, 'w') as f:
                f.write('\n'.join(list(map(lambda x: '\t'.join(list(map(str, x))), data))))
            cp.session['download_files']['query'] = query_file
            page = self.load_webpage('query_result_page', query_result_table=html_data)

        except (err.InvalidSQLError, err.TableAccessError) as e:
            page = self.load_webpage('query_result_page', error=e.message)
        return page

    @cp.expose
    def select_specimen(self, access_code):
        """ Display the page for generating new Aliquot IDs for a particular study """
        with Database(testing=self.testing) as db:
            doc = db.get_docs(access_code=access_code).first()
            data, header = db.execute(fmt.SELECT_SPECIMEN_QUERY.format(StudyName=doc.study_name))
        specimen_table = fmt.build_clickable_table(header, data, 'query_generate_aliquot_id_page',
                                                   {'AccessCode': access_code},
                                                   {'SpecimenID': 0})
        page = self.load_webpage('query_select_specimen_page', specimen_table=specimen_table)
        return page

    @cp.expose
    def generate_aliquot_id(self, AccessCode=None, SpecimenID=None, AliquotWeight=None):
        """
        Page for handling generation of new AliquotIDs for a given study
        ==================================================================
        :AccessCode: The access_code for the study the new id is to be associated with
        :SpecimenID: The ID string of the specimen the new aliquot is taken from
        :AliquotWeight: The weight of the new aliquot to generate an ID for

        Depending on how a user is getting to this page the arguments vary. When initially
        reaching it from `select_specimen`, :AccessCode: and :SpecimenID: are passed in.
        When generate ID is clicked it reloads this page but this time with only AliquotID as
        an argument. This it to make it more convenient to generate mutliple IDs in a row.
        """
        # Load args from the last time this page was loaded
        if AccessCode is None:
            (AccessCode, SpecimenID) = cp.session['generate_aliquot_id']

        # Create the new ID and add it to the database
        success = ''
        error = ''
        with Database(testing=self.testing, owner=self.get_user()) as db:
            if AliquotWeight is not None:
                # Check that the value provided is numeric
                if AliquotWeight.replace('.', '').isnumeric():
                    cp.log("Got weight ", AliquotWeight)
                    doc = db.get_docs(access_code=AccessCode, owner=self.get_user()).first()
                    self.monitor.get_db_lock().acquire()
                    new_id = db.generate_aliquot_id(doc.study_name, SpecimenID, AliquotWeight)
                    self.monitor.get_db_lock().release()
                    success = f'New ID is {new_id} for Aliquot with weight {AliquotWeight}'
                else:
                    error = f'Weight {AliquotWeight} is not a number'

            doc = db.get_docs(access_code=AccessCode, owner=self.get_user()).first()
            cp.log(AccessCode)
            # Get the SQL id of the Specimen this should be associated with
            data, header = db.execute(fmt.SELECT_COLUMN_SPECIMEN_QUERY.format(column='`idSpecimen`',
                                                                              StudyName=doc.study_name,
                                                                              SpecimenID=SpecimenID),
                                      False)
            idSpecimen = data[0][0]
            data, header = db.execute(fmt.SELECT_ALIQUOT_QUERY.format(idSpecimen=idSpecimen))
        aliquot_table = fmt.build_clickable_table(header, data, 'query_generate_sample_id_page',
                                                  {'AccessCode': AccessCode},
                                                  {'AliquotID': 0})

        page = self.load_webpage('query_generate_aliquot_id_page',
                                 success=success,
                                 error=error,
                                 access_code=AccessCode,
                                 aliquot_table=aliquot_table,
                                 SpecimenID=SpecimenID)
        # Store the args for the next page loading
        cp.session['generate_aliquot_id'] = (AccessCode, SpecimenID)
        return page

    @cp.expose
    def generate_sample_id(self, AccessCode=None, AliquotID=None, **kwargs):
        """
        Page for handling generation of new SpecimenIDs for a given study
        ==================================================================
        :AccessCode: The access_code for the study the new id is to be associated with
        :SpecimenID: The ID string of the specimen the new aliquot is taken from
        :kwargs: Contains mutliple arguments relating to a new sample. There are a lot
        so it's neater to take them in and pass them to `Database.generate_sample_id`
        as a dict.
        The required columns are:
            - SampleToolVersion
            - SampleTool
            - SampleConditions
            - DatePerformed
            - SampleProcessor
            - SampleProtocolInformation
            - SampleProtocolID

        The way this page functions is largely the same as generate_aliquot_id.
        The only difference is all the above arguments are passed rather than just AliquotWeight
        """

        # Load args from the last time this page was loaded
        if AccessCode is None:
            (AccessCode, AliquotID) = cp.session['generate_sample_id']

        # Create the new ID and add it to the database
        success = ''
        if kwargs.get('SampleToolVersion') is not None:
            with Database(testing=self.testing, owner=self.get_user()) as db:
                doc = db.get_docs(access_code=AccessCode).first()
                self.monitor.get_db_lock().acquire()
                new_id = db.generate_sample_id(doc.study_name, AliquotID, **kwargs)
                self.monitor.get_db_lock().release()
            success = f'New ID is {new_id} for Sample with processor {kwargs["SampleProcessor"]}'

        # Build the table of Samples
        with Database(testing=self.testing) as db:
            doc = db.get_docs(access_code=AccessCode).first()
            # Get the SQL id of the Aliquot this should be associated with
            data, header = db.execute(fmt.GET_ALIQUOT_QUERY.format(column='idAliquot',
                                                                   AliquotID=AliquotID),
                                      False)
            idAliquot = data[0][0]
            data, header = db.execute(fmt.SELECT_SAMPLE_QUERY.format(idAliquot=idAliquot))

        # There is not ID generation for RawData currently so the table links go nowhere
        sample_table = fmt.build_clickable_table(header, data, '#')

        page = self.load_webpage('query_generate_sample_id_page',
                                 success=success,
                                 access_code=AccessCode,
                                 sample_table=sample_table,
                                 AliquotID=AliquotID)
        # Store the args for the next page loading
        cp.session['generate_sample_id'] = (AccessCode, AliquotID)
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSserver(MMEDSbase):
    def __init__(self):
        super().__init__()
        self.download = MMEDSdownload()
        self.analysis = MMEDSanalysis()
        self.upload = MMEDSupload()
        self.auth = MMEDSauthentication()
        self.study = MMEDSstudy()
        self.query = MMEDSquery()
        cp.log("Created sub servers")

    def load_webpage(self, page, **kwargs):
        """
        Add the highlighting for this section of the website as well as other relevant arguments
        """
        if kwargs.get('home_selected') is None:
            kwargs['home_selected'] = 'w3-text-blue'
        return super().load_webpage(page, **kwargs)

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

            # TODO: TEmporary for figuring this out

            path = fig.DATABASE_DIR
            filename = cp.session['user']
            # Create the filename
            temp_dir = Path(path) / Path(filename).name

            # Ensure there is not already a file with the same name
            while temp_dir.is_dir():
                temp_dir = Path(path) / '_'.join([fig.get_salt(5), Path(filename).name])
            temp_dir.mkdir()
            cp.session['temp_dir'] = temp_dir  # tempfile.TemporaryDirectory()
            cp.session['working_dir'] = Path(cp.session['temp_dir'])

            cp.session['processes'] = {}
            cp.session['download_files'] = {}
            cp.session['uploaded_files'] = {}
            cp.session['subject_ids'] = None
            page = self.load_webpage('home', title='Welcome to Mmeds')
            cp.log('Login Successful')
        except err.InvalidLoginError as e:
            page = self.load_webpage('login', error=e.message)
        return page

    def exit(self):
        cp.log('{} exiting'.format(self))
        cp.engine.exit()

    @cp.expose
    def index(self):
        """ Home page of the application """
        cp.log("loading page as", getpass.getuser())
        if cp.session.get('user'):
            page = self.load_webpage('home')
        else:
            page = self.load_webpage('login')
        return page
