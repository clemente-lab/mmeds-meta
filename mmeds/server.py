import cherrypy as cp
import getpass
from datetime import datetime
from cherrypy.lib import static
from pathlib import Path
from functools import wraps
from inspect import isfunction
from copy import deepcopy

import mmeds.error as err
import mmeds.util as util
import mmeds.config as fig
import mmeds.formatter as fmt

from mmeds.validate import Validator, valid_additional_file
from mmeds.util import (create_local_copy, SafeDict, load_mmeds_stats, simplified_to_full)
from mmeds.config import UPLOADED_FP, HTML_PAGES, HTML_ARGS, SERVER_PATH
from mmeds.authentication import (validate_password, check_username, check_password, check_privileges,
                                  add_user, reset_password, change_password)
from mmeds.database.database import Database
from mmeds.spawn import handle_modify_data, Watcher
from mmeds.logging import Logger


def catch_server_errors(page_method):
    """
    Handles LoggedOutError, and HTTPErrors for all mmeds pages.
    Acts as a wrapper function, meaning it automatically wraps the body of the function
    it is a decorator on.
    """
    @wraps(page_method)
    def wrapper(*a, **kwargs):
        try:
            # Strip any whitespace surrounding input fields
            cleaned_kwargs = {}
            for key, value in kwargs.items():
                if isinstance(value, str):
                    cleaned_kwargs[key] = value.strip()
                else:
                    cleaned_kwargs[key] = value
            return page_method(*a, **cleaned_kwargs)
        except err.LoggedOutError:
            body = HTML_PAGES['login'][0].read_text()
            args = deepcopy(HTML_ARGS)
            args['body'] = body.format(**args)
            # Add the mmeds stats
            args.update(load_mmeds_stats())
            return HTML_PAGES['logged_out_template'].read_text().format(**args)
    return wrapper


def decorate_all_methods(decorator):
    """
    Applies the given decorator to all methods of a class. In the mmeds server it's used
    to wrap each webpage with the `catch_server_errors` function.
    """
    def apply_decorator(cls):
        for k, m in cls.__dict__.items():
            if isfunction(m):
                setattr(cls, k, decorator(m))
        return cls
    return apply_decorator


class MMEDSbase:
    """
    The base class inherited by all mmeds server classes.
    Contains no exposed webpages, only internal functionality used by mutliple pages.
    """

    def __init__(self):
        """
        Creates a connection from the webpage to the watcher process to allow
        for information transfer via the queue
        """
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
        Return the current user. Raises a LoggedOutError if a current user isn't found.
        This error is caught by the `catch_server_errors` decorator allowing it to
        return the Logged out webpage to the user rather than an error.
        """
        try:
            return cp.session['user']
        except KeyError:
            cp.log('Get user failed')
            raise err.LoggedOutError('No user logged in')

    def get_dir(self):
        """
        Return the current user. Delete them from the user list if session data is unavailable.
        Functions similar to `get_user`, Both ensure that someone is properly logged in.
        """
        try:
            return cp.session['working_dir']
        except KeyError:
            raise err.LoggedOutError('No user logged in')

    def get_privilege(self):
        """
        Get's the privilege level of the current user. Right now there are only two levels.
        0 for general users and 1 for lab members. This affects some aspects of how the
        webpages load: What studies are shown, what options are available, etc.
        """
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
            db.check_upload(access_code, not self.get_privilege())
            files, path = db.get_mongo_files(access_code, not self.get_privilege())
        return files

    def load_webpage(self, page, **kwargs):
        """
        Load the requested HTML page, adding the header and topbar if necessary as well
        as any formatting arguments. This is the base method and includes most of the functionality
        but each section of the web app has it's own wrapper around this method to add formatting
        specific to that part of the application.
        """
        try:
            # Check if user needs to reset their password
            reset = False
            if HTML_PAGES[page][1]:
                try:
                    # Check in active dictionary
                    reset = cp.session['reset_needed']
                except AttributeError:
                    # Check in sql database
                    if kwargs.get('user') is not None:
                        user = kwargs.get('user')
                    else:
                        user = self.get_user()
                    with Database(owner=user, testing=self.testing) as db:
                        reset = db.get_reset_needed()
            if reset:
                Logger.error(page)
                page = 'auth_change_password'
                kwargs['error'] = [(
                    'Password change required. Your temporary password has been emailed to you.')]

            path, header = HTML_PAGES[page]

            # Handle any user alerts messages
            kwargs = util.format_alerts(kwargs)

            # Predefined arguments to format in
            args = SafeDict(HTML_ARGS)

            # Add the arguments included in this format call
            args.update(kwargs)

            # Add the mmeds stats
            args.update(load_mmeds_stats())

            # If a user is logged in, load the side bar
            if header:
                template = HTML_PAGES['logged_in_template'].read_text()
                if args.get('user') is None:
                    args['user'] = self.get_user()
                    args['dir'] = self.get_dir()
            else:
                template = HTML_PAGES['logged_out_template'].read_text()

            # Load the body of the requested webpage
            body = path.read_text(encoding='utf-8')

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


@decorate_all_methods(catch_server_errors)
class MMEDSdownload(MMEDSbase):
    """
    The section of the application dedicated to downloading things. The most significant method is
    `download_file`. It is generally what's linked to from any webpage where the user is selecting
    a download.
    """
    def __init__(self):
        super().__init__()

    ########################################
    #            Download Pages            #
    ########################################

    @cp.expose
    def download_file(self, file_name):
        """
        Used to provide downloads to the user. The path to the file must first be added to
        the `cp.session['download_files']` dictionary with the `file_name` as the key and
        the path to the file on disk as the value.
        """
        return static.serve_file(cp.session['download_files'][file_name], 'application/x-download',
                                 'attachment', Path(cp.session['download_files'][file_name]).name)

    @cp.expose
    def download_multiple_ids(self, studyName, idType):
        """
        Generate a file containing the requested IDs and return it for download
        Arguably the call to Database should happen on the caller webpage and just link
        to `download_file` but if it's going to be used it multiple locations on the
        application maybe this does make sense. Who knows.
        """
        with Database(path=self.get_dir(), testing=self.testing, owner=self.get_user()) as db:
            id_file = db.create_ids_file(studyName, idType)

        return static.serve_file(id_file, 'application/x-download', 'attachment', id_file.name)


@decorate_all_methods(catch_server_errors)
class MMEDSstudy(MMEDSbase):
    """
    The section of the web application dedicated to interacting with studies already uploaded to MMEDS.
    """
    def __init__(self):
        super().__init__()

    def load_webpage(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        # Each of the app sections do this. It adds formatting to highlight the button on
        # the side bar that matches the section of the application the user is in
        # Some of the other `load_webpage` wrappers do more.
        if kwargs.get('study_selected') is None:
            kwargs['study_selected'] = 'w3-blue'
        return super().load_webpage(page, **kwargs)

    @cp.expose
    def select_study(self):
        """
        Allows authorized user accounts to access uploaded studies. Users with privilege 0 are
        authorized only to see studies they have uploaded, or studies that have been made public.
        Users with privilege 1 can see all the studies.
        """
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
    """
    This is the largest section of the application. It is dedicated to managing
    user data and metadata uploads. So much functionality is packed in here that
    it requires some non-webpage helper methods. Possibly it could be broken up
    into multiple classed in the future but for now I've tried to roughly organize
    it into several sections based on the method's utility.
    """
    def __init__(self):
        super().__init__()
    ########################################
    #         Upload Functionality         #
    ########################################

    def load_webpage(self, page, **kwargs):
        """
        Add the highlighting for this section of the website
        NOTE: If MMEDS moves to Python 3.10 at some point I think this
        method could be cleaned up significantly if it was converted into
        a pattern matching switch statement instead of all these gross
        if-else blocks.
        """
        if kwargs.get('upload_selected') is None:
            kwargs['upload_selected'] = 'w3-blue'

        # Handle what input forms should appear based on previous selections
        if cp.session.get('upload_type') == 'qiime':
            if cp.session.get('barcodes_type') == 'dual':
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

    def run_validate(self, myMetaData, simplified):
        """
        Run validate_mapping_file and return the results
        """
        cp.log('In run validate')

        # Check the file that's uploaded is a valid file type.
        # TODO Expand this to allow .xls and .xlsx files.
        valid_extensions = ['txt', 'csv', 'tsv']
        file_extension = myMetaData.filename.split('.')[-1]
        if file_extension not in valid_extensions:
            raise err.MetaDataError('{} is not a valid filetype.'.format(file_extension))

        # Create a copy of the MetaData
        metadata_copy = create_local_copy(myMetaData.file, myMetaData.filename, self.get_dir())

        # If the metadata is simplified, convert it to full before performing validation
        if simplified:
            # Overwrite the metadata_copy
            simplified_to_full(metadata_copy, metadata_copy, cp.session['metadata_type'], cp.session['subject_type'])

        # Store the copy's location
        cp.session['uploaded_files'][cp.session['metadata_type']] = metadata_copy

        cp.log('before validator creation')
        # Create an instance of the Validator class with all the appropriate parameters
        valid = Validator(metadata_copy,
                          cp.session['study_name'],
                          cp.session['metadata_type'],
                          cp.session['subject_ids'],
                          cp.session['subject_type'],
                          cp.session.get('barcodes_type'))
        cp.log('before validator run')

        # Check the metadata file for errors
        errors, warnings, subjects = valid.run()

        # The database for any issues with previous uploads for the subject metadata
        with Database('.', owner=self.get_user(), testing=self.testing) as db:
            try:
                # Perform additional checks that the Validator has insufficient information
                # to perform during it's run
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
        """ Load the files passed in by the user. """
        files = {}
        for key, value in kwargs.items():
            if value is not None:
                file_copy = create_local_copy(value.file, value.filename, self.get_dir())
                files[key] = file_copy
        return files

    def handle_errors_warnings(self, metadata_copy, errors, warnings):
        """
        Handle loading different pages depending if there are metadata errors, warnings, or neither.
        NOTE: This is another place that could benefit from switch statements.
        """

        # Get data from upload
        try:
            df = cp.session['subject_ids']
        except KeyError:
            df = None

        # Append Host Subject IDs to list without duplicates
        sub_count = 0
        if cp.session['subject_type'] == 'animal':
            subjectName = 'AnimalSubjectID'
        else:
            subjectName = 'HostSubjectId'
        if df is not None and subjectName in df.columns:
            sub_count = df[subjectName].nunique()

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
            page = self.load_webpage('upload_metadata_confirmation',
                                     title='Warnings',
                                     warning=warnings,
                                     confirmation_message='Ignore warnings and proceed?',
                                     yes_page='continue_metadata_upload',
                                     no_page='upload_subject_metadata')
        else:
            # If it's the subject metadata file return the page for uploading the specimen metadata
            if cp.session['metadata_type'] == 'subject':
                success_str = 'Subject table reviewed successfully'
                if df is not None:
                    success_str += ' and found {} unique subjects'.format(sub_count)

                page = self.load_webpage('upload_metadata_confirmation',
                                         title='Upload Metadata',
                                         success=success_str,
                                         confirmation_message='Confirm this data and continue?',
                                         yes_page='continue_metadata_upload',
                                         no_page='upload_subject_metadata')
                # Otherwise proceed to uploading data files
            elif cp.session['metadata_type'] == 'specimen':
                # If it's the specimen metadata file, save the type of barcodes
                # And return the page for uploading data files
                page = self.upload_data()
        return page

    ########################
    # General Upload Pages #
    ########################

    @cp.expose
    def user_guide(self):
        """ Page for the guide for the user on how to upload """
        page = self.load_webpage('user_guide',
                                 title='Upload Guide')
        return page

    @cp.expose
    def simple_guide(self):
        """ Page for the user guide for simplified uploads """
        page = self.load_webpage('simple_guide',
                                 title='Upload Guide')
        return page

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
        """
        Modify the data of an existing upload.
        :myData: The new data file to upload
        :data_type: The key for the file to be replaced
        :access_code: The access_code for the study to replace a file in

        NOTE: This method should probably be moved to the MMEDSstudy section
        and split into two pages. The first would have a drop down where the
        user can select the Study to modify. The second would have a drop down
        to select the file to be replaced as well as the upload form for the
        new file.
        """
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
            page = self.load_webpage('home', error=e.message)
        return page

    @cp.expose
    def upload_page(self):
        """
        Page for selecting upload type or modifying upload.
        This is the root page that a user lands on when they select
        'uploade' from the navigation panel.
        """
        cp.log('Access upload page')
        with Database(testing=self.testing) as db:
            studies = db.get_all_user_studies(self.get_user())
            study_dropdown = fmt.build_study_code_dropdown(studies)

        # Note: I don't love this but I don't have a better solution
        cp.session['download_files']['user_guide'] = fig.USER_GUIDE
        cp.session['download_files']['Subject_template'] = fig.SUBJECT_TEMPLATE
        cp.session['download_files']['Specimen_template'] = fig.SPECIMEN_TEMPLATE
        cp.session['download_files']['Subject_example'] = fig.TEST_SUBJECT
        cp.session['download_files']['Specimen_example'] = fig.TEST_SPECIMEN
        cp.session['metadata_type'] = 'subject'
        page = self.load_webpage('upload_select_page',
                                 user_studies=study_dropdown,
                                 title='Upload Type')
        return page

    #########################
    # Metadata Upload Pages #
    #########################

    @cp.expose
    def upload_subject_metadata(self, subjectType=None, studyName=None):
        """
        Page for uploading subject metadata data.
        This is the first thing to be uploaded for a particular study.
        """

        if subjectType is None and studyName is None:
            # If neither of these value are being passed in from the webpage then the
            # page is being reset to here from a further point in the upload process,
            # pull data from cp.session and proceed.
            subjectType = cp.session['subject_type']
            studyName = cp.session['study_name']

        try:
            cp.session['study_name'] = studyName
            cp.session['metadata_type'] = 'subject'
            cp.session['subject_type'] = subjectType

            with Database(path='.', testing=self.testing, owner=self.get_user()) as db:
                db.check_study_name(studyName)
                page = self.load_webpage('upload_subject_file',
                                         title='Upload Subject Metadata')

        # If the study name is already in use instruct the user to try something else.
        except(err.StudyNameError) as e:
            with Database(testing=self.testing) as db:
                studies = db.get_all_user_studies(self.get_user())
                study_dropdown = fmt.build_study_code_dropdown(studies)
                page = self.load_webpage('upload_select_page',
                                         title='Upload Type',
                                         user_studies=study_dropdown,
                                         error=e.message)
        return page

    @cp.expose
    def upload_specimen_metadata(self, uploadType, studyName):
        """
        Page for uploading specimen metadata files.
        This happens after a successful subject metadata upload.
        """
        try:
            cp.session['metadata_type'] = 'specimen'
            cp.session['study_name'] = studyName
            cp.session['upload_type'] = uploadType

            with Database(path='.', testing=self.testing, owner=self.get_user()) as db:
                db.check_study_name(studyName)

            # Add the success message if applicable
            page = self.load_webpage('upload_specimen_file',
                                     title='Upload Metadata',
                                     success='Subject table uploaded successfully',
                                     metadata_type=cp.session['metadata_type'].capitalize(),
                                     version=uploadType)

        # Not 100% sure this check still needs to be here, as the study name
        # should've already been checked at this point.
        except(err.StudyNameError) as e:
            with Database(testing=self.testing) as db:
                studies = db.get_all_user_studies(self.get_user())
                study_dropdown = fmt.build_study_code_dropdown(studies)
                page = self.load_webpage('upload_select_page',
                                         title='Upload Type',
                                         user_studies=study_dropdown,
                                         error=e.message)
        return page

    @cp.expose
    def continue_metadata_upload(self):
        """
        If there are warnings generated for a particular metadata file then the user will
        be presented with a page displaying the warnings as asking the user if they want
        to continue. If there are no warnings this page will take them directly to the
        next appropraite upload page.
        """
        # Only arrive here if there are no errors or warnings proceed to upload the data files
        alert = '{} metadata uploaded successfully'.format(cp.session['metadata_type'].capitalize())

        # Move on to uploading data files
        if cp.session['metadata_type'] == 'specimen':
            # The case for handling uploads of fastq files
            page = self.load_webpage(
                'upload_data_files',
                title='Upload Data',
                success=alert
            )
        # Move on to uploading specimen metadata
        else:
            cp.session['metadata_type'] = 'specimen'
            page = self.load_webpage('upload_specimen_file',
                                     title='Upload Metadata',
                                     success='Subject table uploaded successfully',
                                     metadata_type=cp.session['metadata_type'].capitalize())
        return page

    @cp.expose
    def validate_metadata(self, myMetaData, barcodes_type=None, simplified=False):
        """
        This webpage handles the validation of each metadata file. Using a call to
        the helper method `run_validate`.
        """
        try:
            cp.log('in validate, current metadata {}'.format(cp.session['metadata_type']))
            errors, warnings = self.run_validate(myMetaData, simplified)
            metadata_copy = cp.session['uploaded_files'][cp.session['metadata_type']]

            if barcodes_type is not None:
                cp.session['barcodes_type'] = barcodes_type

            page = self.handle_errors_warnings(metadata_copy, errors, warnings)

        except err.MetaDataError as e:
            page = self.load_webpage(f'upload_{cp.session["metadata_type"]}_file',
                                     title='Upload Metadata',
                                     error=e.message,
                                     metadata_type=cp.session['metadata_type'])
        return page

    @cp.expose
    def additional_metadata(self, accessCode, idType, dataFile, generateID=False):
        """
        Webpage for handling the upload of new metadata related to an existing study.
        """
        success = ''
        error = ''
        cp.log('idType is ')
        cp.log(idType)
        # Ensure that the access code is valid for a particular user
        try:
            self.check_upload(accessCode)
        except err.MissingUploadError as e:
            error = e.message
        else:
            data_file = self.load_data_files(idFile=dataFile)

            if valid_additional_file(data_file['idFile'], idType, generateID):

                # Pass it to the watcher
                self.q.put(('upload-ids', self.get_user(), accessCode, data_file['idFile'], idType, generateID))
                success = f'{idType.capitalize()} Data Upload Initiated.' +\
                    'You will recieve an email when it finishes'
            else:
                error = f'There was an issue with your {idType} file. Please check the example.'
        return self.load_webpage('home', success=success, error=error)

    #####################
    # Data Upload Pages #
    #####################

    @cp.expose
    def upload_data(self):
        """ The page for uploading data files of any type"""

        # Only arrive here if there are no errors or warnings proceed to upload the data files
        alert = 'Specimen metadata uploaded successfully'

        # The case for handling uploads of fastq files
        page = self.load_webpage(
            'upload_data_files',
            title='Upload Data',
            success=alert
        )
        return page

    @cp.expose
    def process_data(self, public=False, **kwargs):
        """ The page for loading data files into the database """
        # Create a unique dir for handling files uploaded by this user
        subject_metadata = Path(cp.session['uploaded_files']['subject'])
        specimen_metadata = Path(cp.session['uploaded_files']['specimen'])

        # Unpack kwargs based on barcode type
        # Add the datafiles that exist as arguments
        if 'otu_table' in kwargs:
            cp.session['upload_type'] = 'sparcc'
        elif 'lefse_table' in kwargs:
            cp.session['upload_type'] = 'lefse'
        else:
            cp.session['upload_type'] = 'qiime'

        # NOTE: More places to update with pattern matched switch statements
        if cp.session['upload_type'] == 'qiime':
            if cp.session['barcodes_type'].startswith('dual'):
                cp.log("Upload is Qiime Dual Barcodes")
                # If have dual barcodes, don't have a reads_type in kwargs so must set it
                datafiles = self.load_data_files(for_reads=kwargs['for_reads'],
                                                 rev_reads=kwargs['rev_reads'],
                                                 for_barcodes=kwargs['barcodes'],
                                                 rev_barcodes=kwargs['rev_barcodes'])
                reads_type = 'paired_end'
                barcodes_type = 'dual_barcodes'
                if cp.session['barcodes_type'].endswith('x'):
                    barcodes_type += '_legacy'
            else:
                cp.log("Upload is Qiime Single Barcodes")
                barcodes_type = 'single_barcodes'
                datafiles = self.load_data_files(for_reads=kwargs['for_reads'],
                                                 rev_reads=kwargs['rev_reads'],
                                                 barcodes=kwargs['barcodes'])
                reads_type = kwargs['reads_type']
        elif cp.session['upload_type'] == 'sparcc':
            cp.log("Upload is SparCC data")
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
            cp.log(f"Upload is LeFSe data with reads type {reads_type}")
            barcodes_type = None

        cp.log("Server putting upload in queue {}".format(id(self.q)))
        # Add the files to be uploaded to the queue for uploads
        # This will be handled by the Watcher class found in spawn.py
        self.q.put(('upload', cp.session['study_name'], subject_metadata, cp.session['subject_type'],
                    specimen_metadata, self.get_user(), reads_type, barcodes_type, datafiles,
                    cp.session['subject_type'], public))

        return self.load_webpage('home', success='Upload Initiated. You will recieve an email when this finishes')


@decorate_all_methods(catch_server_errors)
class MMEDSauthentication(MMEDSbase):
    """
    This is the section of the web application that handles use accounts and account management.
    """
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
    def public_guide(self):
        """ Return the public user guide """
        return self.load_webpage('user_guide_public', title='Upload Guide')

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
        :username: The username selected by the user. Must be unique to create the account.
        :password1: First copy of the user's desired password.
        :password2: Second copy of the user's desire password, must match :password1:.
        :email: The email address the user is signing up with.
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
        """
        Load page for changing the user's password
        NOTE: Not sure if this is still used? I think it's been superseded by `change_password`.
        """
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
            # Force the user to logout
            cp.lib.sessions.expire()
            validate_password(self.get_user(), password0, testing=self.testing)
            # Check the two copies of the new password match
            check_password(password1, password2)
            change_password(self.get_user(), password1, testing=self.testing)
            page = self.load_webpage('auth_change_password', success='Your password was successfully changed.')
            cp.session['reset_needed'] = 0
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
            with Database(owner=username, testing=self.testing) as db:
                db.set_reset_needed(True)
        except err.NoResultError:
            page = self.load_webpage('login', error='No account exists with the provided username and email.')
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSanalysis(MMEDSbase):
    """
    This is the section of the web app that handles selecting and viewing analyses.
    """
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
    def run_analysis(self, studyName, analysis_method, config, runOnNode=None):
        """
        Run analysis on the specified study
        ----------------------------------------
        :access_code: The code that identifies the dataset to run the tool on
        :analysis_method: The tool and analysis to run on the chosen dataset
        :config: The config file in some format. This is an ongoing issue.
        :runOnNode: A value only selectable by those with a Privilege of 1
            When selected the analysis will run directly on the MMEDS node
            rather than being submitted to the job queue.
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

            with Database(testing=self.testing) as db:
                access_code = db.get_access_code_from_study_name(studyName, self.get_user())
                Logger.error(access_code)

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
        study_html = ''' <tr class="w3-hover-blue">
            <th>
            <a href="{select_specimen_page}?access_code={access_code}"> {study_name} </a>
            </th>
            <th>{date_created}</th>
        </tr> '''

        id_study_html = '<option value="{study_name}">{study_name}</option>'

        # Get all the studies that are available to the current user
        with Database(testing=self.testing, owner=self.get_user()) as db:
            studies = db.get_all_user_studies(self.get_user())

        # Build an HTML list of the studies
        study_list = []
        id_study_list = []
        for study in studies:
            study_list.append(study_html.format(study_name=study.study_name,
                                                select_specimen_page=SERVER_PATH + 'query/select_specimen',
                                                access_code=study.access_code,
                                                date_created=study.created,
                                                ))
            id_study_list.append(id_study_html.format(study_name=study.study_name))

        # Add unhide any privileged options
        if check_privileges(self.get_user(), self.testing):
            page = self.load_webpage('analysis_select_tool',
                                     title='Select Analysis',
                                     user_studies='\n'.join(study_list),
                                     id_user_studies='\n'.join(id_study_list),
                                     privilege=''
                                     )
        else:
            page = self.load_webpage('analysis_select_tool',
                                     title='Select Analysis',
                                     user_studies='\n'.join(study_list),
                                     id_user_studies='\n'.join(id_study_list)
                                     )
        return page


@decorate_all_methods(catch_server_errors)
class MMEDSquery(MMEDSbase):
    """
    The section of the web app that handles interaction with the SQL database.
    Performing queries, requesting data dumps (when implemented), etc
    It also includes the web pages for adding Samples/Aliquots to an existing study
    Arguably that should be in `MMEDSupload`, but that class is already more that
    twice the size of any other.
    """
    def __init__(self):
        super().__init__()

    def load_webpage(self, page, **kwargs):
        """ Add the highlighting for this section of the website """
        if kwargs.get('query_selected') is None:
            kwargs['query_selected'] = 'w3-blue'
        return super().load_webpage(page, **kwargs)

    @cp.expose
    def query_select(self):
        """
        The base page for the Query section of the application. From here the user can select
        from several forms for either
        1) Running a query against the MySQL
        2) Downloading all the IDs for for Samples or Aliquots in a given study
        3) Uploading new IDs for Samples or Aliquots to a given study
        """
        study_html = ''' <tr class="w3-hover-blue">
            <th>
            <a href="{select_specimen_page}?access_code={access_code}"> {study_name} </a>
            </th>
            <th>{date_created}</th>
        </tr> '''

        id_study_html = '<option value="{study_name}">{study_name}</option>'

        with Database(testing=self.testing) as db:
            studies = db.get_all_user_studies(self.get_user())

        # This exact code block appears elsewhere in server.py
        # It might be worth moving it into it's own utility method
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
    def generate_aliquot_id(self, AccessCode=None, SpecimenID=None, **kwargs):
        """
        Page for handling generation of new AliquotIDs for a given study
        ==================================================================
        :AccessCode: The access_code for the study the new id is to be associated with
        :SpecimenID: The ID string of the specimen the new aliquot is taken from
        :kwargs: The other keyword arguments, passed as a dictionary

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
            if 'AliquotWeight' in kwargs.keys():
                # Check that the value provided is numeric
                if kwargs['AliquotWeight'].replace('.', '').isnumeric():
                    doc = db.get_docs(access_code=AccessCode, owner=self.get_user()).first()
                    self.monitor.get_db_lock().acquire()
                    new_id = db.generate_aliquot_id(True, doc.study_name, SpecimenID, **kwargs)
                    self.monitor.get_db_lock().release()
                    success = f'New ID is {new_id} for Aliquot with weight {kwargs["AliquotWeight"]}'
                else:
                    error = f'Weight {kwargs["AliquotWeight"]} is not a number'

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
            - SampleWeight
            - SampleWeightUnit
            - StorageInstitution
            - StorageFreezer

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
                new_id = db.generate_sample_id(True, doc.study_name, AliquotID, **kwargs)
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
    """
    The final level of the web app. This inherits from MMEDSbase and has an instance
    of each of the sections of the app as a property. When accessing the web app those
    sections are apparent in the URL.
    This class also directly handles users logging in and logging out, as well as loading
    the application home page. The log in / log out functionality should arguably be
    moved to MMEDSauthentication.
    """
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
            path = fig.DATABASE_DIR
            filename = cp.session['user']
            # Create the filename
            temp_dir = Path(path) / 'temp_dir' / '__'.join([Path(filename).name,
                                                            str(datetime.utcnow().strftime("%Y-%m-%d-%H:%M")),
                                                            '0x'])

            # Ensure there is not already a file with the same name
            temp_idx = 0
            while temp_dir.is_dir():
                temp_dir = Path(str(temp_dir).replace(f'__{temp_idx}x', f'__{temp_idx + 1}x'))
                temp_idx += 1
            temp_dir.mkdir(parents=True)
            cp.session['temp_dir'] = temp_dir
            cp.session['working_dir'] = Path(cp.session['temp_dir'])

            cp.session['processes'] = {}
            cp.session['download_files'] = {}
            cp.session['uploaded_files'] = {}
            cp.session['subject_ids'] = None
            with Database(owner=username, testing=self.testing) as db:
                cp.session['reset_needed'] = db.get_reset_needed()
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
