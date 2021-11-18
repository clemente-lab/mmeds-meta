from pathlib import Path
from random import choice
from pandas import read_csv, Timestamp
from collections import defaultdict
from socket import getfqdn, gethostname
import cherrypy as cp
import pymysql as pms
import mmeds.secrets as sec
import mmeds.html as html
import mmeds.resources as resources
import mmeds
import hashlib
import re


# Check where this code is being run
TESTING = not ('chimera' in getfqdn().split('.'))
# If not running on web01, can't connect to databases
IS_PRODUCTION = 'web01' in getfqdn().split('.')
if TESTING:
    ROOT = Path(mmeds.__file__).parent.resolve()
    HTML_DIR = Path(html.__file__).parent.resolve()
    STORAGE_DIR = Path(resources.__file__).parent.resolve()
    # If apache is trying to access apache's home directory for `mmeds_server_data` rather than your user account's home
    # you may need to hardcode the path here
    # TODO: Add mmeds configuration options for DATABASE_DIR
    if gethostname() == 'fedora-y70':
        DATABASE_DIR = Path('/home/david') / 'mmeds_server_data'
    elif gethostname() == 'Hal':
        DATABASE_DIR = Path('/home/matt') / 'mmeds_server_data'
    elif gethostname() == 'adam-Inspiron-15-7000':
        DATABASE_DIR = Path('/home/adamcantor22') / 'mmeds_server_data'
    else:
        DATABASE_DIR = Path().home() / 'mmeds_server_data'
    SERVER_PATH = 'http://localhost/myapp/'
    CSS_DIR = 'http://localhost/CSS/'
    IMAGE_PATH = str(CSS_DIR) + '/'
else:
    ROOT = Path('/hpc/users/mmedsadmin/www/mmeds-meta/')
    HTML_DIR = ROOT / 'mmeds/html'
    CSS_DIR = ROOT / 'mmeds/CSS'
    STORAGE_DIR = ROOT / 'mmeds/resources'
    WWW_ROOT = "https://mmedsadmin.u.hpc.mssm.edu/"
    SERVER_ROOT = WWW_ROOT + "mmeds_app/"
    # Replace the old version
    SERVER_PATH = SERVER_ROOT + 'app.wsgi/'
    # Load the path to where images are hosted
    IMAGE_PATH = WWW_ROOT + 'mmeds/CSS/'

    # We're on web01 and using MMEDs out of if it's project diredctory
    if IS_PRODUCTION:
        DATABASE_DIR = Path('/sc/arion/projects/MMEDS/mmeds_server_data')
    # We're on Matt's login node, see above TODO for needed improvement
    else:
        DATABASE_DIR = Path('/hpc/users/stapym01') / 'mmeds_server_data'


STUDIES_DIR = DATABASE_DIR / 'studies'
SESSION_PATH = DATABASE_DIR / 'CherryPySessions'

############################
# CONFIGURE SERVER GLOBALS #
############################


# Configuration for the CherryPy server
CONFIG = {
    'global': {
        'log.access_file': str(DATABASE_DIR / 'site_access.log'),
        'log.error_file': str(DATABASE_DIR / 'site_error.log'),
        'tools.sessions.storage_class': cp.lib.sessions.FileSession,
        'tools.sessions.storage_path': SESSION_PATH,
        'tools.sessions.name': 'latest_sessions',
        'tools.sessions.on': True,
        'tools.sessions.timeout': 15,
        'tools.compress.gzip': True,
        # 'environment' : 'production'
    },
    # Content in this directory will be made directly
    # available on the web server
    'mmeds/CSS': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': IMAGE_PATH
    },
    # This sets up the https security
    '/protected/area': {
        'tools.auth_digest': True,
        'tools.auth_digest.realm': sec.SERVER_HOST,
        'tools.auth_digest.key': sec.DIGEST_KEY,
    }
}

# Additional settings for when testing
TESTING_CONFIG = {
    'server.socket_host': sec.SERVER_HOST,
    'server.socket_port': sec.SERVER_PORT,
    'server.socket_timeout': 1_000_000_000,
    'server.max_request_body_size': 10_000_000_000,
    'server.ssl_module': 'builtin',
    'server.ssl_certificate': str(STORAGE_DIR / 'cert.pem'),
    'server.ssl_private_key': str(STORAGE_DIR / 'key.pem'),
    'request.scheme': 'https',
    'Secureheaders.on': True,
    'tools.sessions.secure': True,
}
if TESTING:
    CONFIG['global'].update(TESTING_CONFIG)


# Each page returns a tuple
# (<Path to the page>, <Should the header and topbar be loaded>)
# These link the keys used to identify the HTML pages the server loads
# to the location of the HTML files on disk
HTML_PAGES = {
    # Templates
    'logged_out_template': HTML_DIR / 'logged_out_template.html',
    'logged_in_template': HTML_DIR / 'logged_in_template.html',

    # Authentication Pages
    'login': (HTML_DIR / 'login_body.html', False),
    'forgot_password': (HTML_DIR / 'forgot_password_page.html', False),
    'home': (HTML_DIR / 'home_body.html', True),
    'auth_change_password': (HTML_DIR / 'auth_change_password.html', True),
    'auth_sign_up_page': (HTML_DIR / 'auth_sign_up_page.html', False),
    'user_guide_public': (HTML_DIR / 'user_guide.html', False),

    # Upload Pages
    'user_guide': (HTML_DIR / 'user_guide.html', True),
    'simple_guide': (HTML_DIR / 'simple_guide.html', True),
    'upload_metadata_error': (HTML_DIR / 'upload_metadata_error.html', True),
    'upload_specimen_file': (HTML_DIR / 'upload_specimen_file.html', True),
    'upload_subject_file': (HTML_DIR / 'upload_subject_file.html', True),
    'upload_select_page': (HTML_DIR / 'upload_select_page.html', True),
    'upload_otu_data': (HTML_DIR / 'upload_otu_data.html', True),
    'upload_data_files': (HTML_DIR / 'upload_data_files.html', True),
    'upload_metadata_confirmation': (HTML_DIR / 'upload_metadata_confirmation.html', True),

    # Study Pages
    'study_select_page': (HTML_DIR / 'study_select_page.html', True),
    'study_view_page': (HTML_DIR / 'study_view_page.html', True),

    # Analysis Pages
    'analysis_view_page': (HTML_DIR / 'analysis_view_page.html', True),
    'analysis_select_page': (HTML_DIR / 'analysis_select_page.html', True),
    'analysis_select_tool': (HTML_DIR / 'analysis_select_tool.html', True),

    # Query Pages
    'query_select_page': (HTML_DIR / 'query_select_page.html', True),
    'query_result_page': (HTML_DIR / 'query_result_page.html', True),
    'query_select_specimen_page': (HTML_DIR / 'query_select_specimen_page.html', True),
    'query_generate_aliquot_id_page': (HTML_DIR / 'query_generate_aliquot_id_page.html', True),
    'query_generate_sample_id_page': (HTML_DIR / 'query_generate_sample_id_page.html', True),
}

# Predefined options for formatting webpages are set here
# These link the key names for webpages used in the HTML templates
# To the locations of those webpages on the server and in the server class
HTML_ARGS = {
    'version': '0.1.0',
    'study_count': 0,
    'user_count': 0,
    'analysis_count': 0,
    'query_count': 0,

    # Site Wide
    'title': 'MMEDs Database and Analysis Server',

    # Images
    'favicon': IMAGE_PATH + 'favicon.ico',
    'mount_sinai_logo': IMAGE_PATH + 'Mount_Sinai_Logo.png',
    'mmeds_logo': IMAGE_PATH + 'MMeds_Logo.png',
    'mmeds_logo_big': IMAGE_PATH + 'MMeds_Logo_Big_Transparent.png',

    # Paths to other pages of the website
    'home_page': SERVER_PATH + 'index',
    'login_page': SERVER_PATH + 'login',
    'logout_page': SERVER_PATH + 'auth/logout',
    'upload_page': SERVER_PATH + 'upload/upload_page',
    'analysis_page': SERVER_PATH + 'analysis/analysis_page',
    'study_page': SERVER_PATH + 'study/select_study',
    'account_page': SERVER_PATH + 'auth/input_password',
    'query_page': SERVER_PATH + 'query/query_select',
    'user_guide_page': SERVER_PATH + 'upload/user_guide',
    'simple_guide_page': SERVER_PATH + 'upload/simple_guide',
    'settings_page': '#',

    # Upload Pages
    'upload_subject_metadata_page': SERVER_PATH + 'upload/upload_subject_metadata',
    'upload_specimen_metadata_page': SERVER_PATH + 'upload/upload_specimen_metadata',
    'validate_metadata_page': SERVER_PATH + 'upload/validate_metadata',
    'process_data_page': SERVER_PATH + 'upload/process_data',
    'retry_upload_page': SERVER_PATH + 'upload/retry_upload',
    'continue_metadata_upload': SERVER_PATH + 'upload/continue_metadata_upload',
    'upload_data_page': SERVER_PATH + 'upload/upload_data',
    'upload_modify_page': SERVER_PATH + 'upload/modify_upload',
    'upload_multiple_ids_page': SERVER_PATH + 'upload/upload_multiple_ids',
    'generate_multiple_ids_page': SERVER_PATH + 'upload/generate_multiple_ids',
    'upload_additional_metadata_page': SERVER_PATH + 'upload/additional_metadata',

    # Download Pages
    'download_page': SERVER_PATH + 'download/download_file',
    'download_multiple_ids_page': SERVER_PATH + 'download/download_multiple_ids',

    # Study Pages
    'study_select_page': SERVER_PATH + 'study/select_study',
    'study_view_page': SERVER_PATH + 'study/view_study',

    # Analysis Pages
    'analysis_view_page': SERVER_PATH + 'analysis/view_analysis',

    # Account Pages
    'register_account_page': SERVER_PATH + 'auth/register_account',
    'forgot_password_page': SERVER_PATH + 'auth/password_recovery',
    'submit_recovery_page': SERVER_PATH + 'auth/submit_password_recovery',
    'change_password': SERVER_PATH + 'auth/change_password',
    'sign_up_page': SERVER_PATH + 'auth/sign_up',

    # Query Pages
    'query_result_page': SERVER_PATH + 'query/execute_query',
    'query_select_specimen_page': SERVER_PATH + 'query/select_specimen',
    'query_generate_aliquot_id_page': SERVER_PATH + 'query/generate_aliquot_id',
    'query_generate_sample_id_page': SERVER_PATH + 'query/generate_sample_id',
    'query_result_table': '',

    # Where to insert errors/warnings on a given page
    'error': '',
    'warning': '',
    'success': '',
    'javascript': IMAGE_PATH + 'mmeds.js',
    'stylesheet': IMAGE_PATH + 'stylesheet.css',
    'privilege': 'display:none',

    # Settings for highlighting the section of the web site currently being accessed
    'upload_selected': '',
    'analysis_selected': '',
    'study_selected': '',
    'query_selected': '',
    'home_selected': '',
    'account_selected': '',
    'settings_selected': '',

    # Link to nowhere
    '#': '#',
}

##########################
# CONFIGURE TOOL GLOBALS #
###########################


TOOL_FILES = {
    'child_analysis': ['otu_table'],
    'qiime1': ['data', 'for_reads', 'rev_reads', 'barcodes', 'for_barcodes', 'rev_barcodes', 'metadata'],
    'qiime2': ['data', 'for_reads', 'rev_reads', 'barcodes', 'for_barcodes', 'rev_barcodes', 'metadata'],
    'sparcc': ['otu_table'],
    'lefse': ['lefse_table'],
    'picrust1': ['otu_table'],
    'test': []
}

UPLOADED_FP = 'uploaded_file'
ERROR_FP = 'error_log.tsv'

MODULE_ROOT = DATABASE_DIR.parent / '.modules/modulefiles'

if not DATABASE_DIR.exists():
    try:
        DATABASE_DIR.mkdir()
    except FileExistsError:
        pass

if not STUDIES_DIR.exists():
    try:
        STUDIES_DIR.mkdir()
    except FileExistsError:
        pass

if not SESSION_PATH.exists():
    try:
        SESSION_PATH.mkdir()
    except FileExistsError:
        pass

JOB_TEMPLATE = STORAGE_DIR / 'job_template.lsf'
MMEDS_LOG = DATABASE_DIR / 'mmeds_log.txt'
SQL_LOG = DATABASE_DIR / 'sql_log.txt'
DOCUMENT_LOG = DATABASE_DIR / 'document_log.txt'
STAT_FILE = DATABASE_DIR / 'mmeds_stats.yaml'
PROCESS_LOG_DIR = DATABASE_DIR / 'process_log_dir'
LOG_CONFIG = STORAGE_DIR / 'log_config.yaml'
if not PROCESS_LOG_DIR.exists():
    try:
        PROCESS_LOG_DIR.mkdir()
    except FileExistsError:
        pass
LOG_DIR = DATABASE_DIR
if not LOG_DIR.exists():
    try:
        LOG_DIR.mkdir()
    except FileExistsError:
        pass
CURRENT_PROCESSES = DATABASE_DIR / 'current_processes.yaml'
CONFIG_PARAMETERS = [
    'sampling_depth',
    'metadata',
    'taxa_levels',
    'abundance_threshold',
    'font_size',
    'sub_analysis',
    'additional_analysis',
    'iterations',
    'permutations',
    'type'
]
CONTACT_EMAIL = 'david.wallach@mssm.edu'
MMEDS_EMAIL = 'donotreply.mmeds.server@outlook.com'
TEST_EMAIL = 'mmeds.tester@outlook.com'
SQL_DATABASE = 'mmeds_data1'
DEFAULT_CONFIG = STORAGE_DIR / 'config_file.yaml'
if not TESTING:
    cp.config.update(CONFIG)


##########################
# CONFIGURE TEST GLOBALS #
##########################

TEST_PATH = DATABASE_DIR / 'test_files'
TEST_DIR = DATABASE_DIR / 'mmeds_test_dir'
if not TEST_DIR.exists():
    try:
        TEST_DIR.mkdir()
    except FileExistsError:
        pass
TEST_DIR_0 = DATABASE_DIR / 'mmeds_test_dir0'
if not TEST_DIR_0.exists():
    try:
        TEST_DIR_0.mkdir()
    except FileExistsError:
        pass

TEST_USER = 'testuser'
SERVER_USER = 'serveruser'
TEST_USER_0 = 'testuser0'
TEST_CODE = 'singlereads'
TEST_CODE_SHORT = 'singlereadsshort'
TEST_CODE_PAIRED = 'pairedreads'
TEST_CODE_DEMUX = 'demuxedreads'
TEST_CODE_OTU = 'otutable'
TEST_CODE_LEFSE = 'lefsetable'
TEST_MIXS = str(TEST_PATH / 'test_MIxS.tsv')
TEST_MIXS_MMEDS = str(TEST_PATH / 'MIxS_metadata.tsv')
TEST_OTU = str(TEST_PATH / 'test_otu_table.txt')
TEST_LEFSE = str(TEST_PATH / 'test_lefse_table.txt')
TEST_CONFIG = str(TEST_PATH / 'test_config_file.yaml')
TEST_CONFIG_SUB = str(TEST_PATH / 'sub_config_file.yaml')
TEST_CONFIG_1 = str(TEST_PATH / 'test_config_file_fail1.yaml')
TEST_CONFIG_2 = str(TEST_PATH / 'test_config_file_fail2.yaml')
TEST_CONFIG_3 = str(TEST_PATH / 'test_config_file_fail3.yaml')
TEST_CONFIG_ALL = str(TEST_PATH / 'test_config_all.yaml')
TEST_ANIMAL_CONFIG = str(TEST_PATH / 'test_config_animal.yaml')
TEST_MAPPING = str(TEST_PATH / 'qiime_mapping_file.tsv')
TEST_MAPPING_DUAL = str(TEST_PATH / 'qiime_mapping_file_dual.tsv')
TEST_PHENIQS_DIR = str(TEST_PATH / 'test_pheniqs')
TEST_STRIPPED_OUTPUT_DIR = str(TEST_PATH / 'test_stripped')
TEST_STRIPPED_DIRS = [
    str(TEST_PATH / 'test_stripped_0'),
    str(TEST_PATH / 'test_stripped_1'),
    str(TEST_PATH / 'test_stripped_2')
]
TEST_PHENIQS_MAPPING = str(TEST_PATH / 'test_pheniqs_mapping_file.tsv')
TEST_SPECIMEN = str(TEST_PATH / 'test_specimen.tsv')
TEST_SPECIMEN_SIMPLIFIED = str(TEST_PATH / 'test_specimen_simplified.tsv')
TEST_SPECIMEN_ALT = str(TEST_PATH / 'test_specimen_alt.tsv')
TEST_SPECIMEN_ERROR = str(TEST_PATH / 'validation_files/test_specimen_error.tsv')
TEST_SPECIMEN_WARN = str(TEST_PATH / 'validation_files/test_specimen_warn.tsv')
TEST_SPECIMEN_SHORT = str(TEST_PATH / 'test_specimen_short.tsv')
TEST_SPECIMEN_SHORT_DUAL = str(TEST_PATH / 'test_specimen_short_dual.tsv')
TEST_SPECIMEN_SHORT_WARN = str(TEST_PATH / 'validation_files/test_specimen_short_warn.tsv')
TEST_SUBJECT = str(TEST_PATH / 'test_subject.tsv')
TEST_SUBJECT_SIMPLIFIED = str(TEST_PATH / 'test_subject_simplified.tsv')
TEST_ADD_SUBJECT = str(TEST_PATH / 'test_add_subject.tsv')
TEST_ANIMAL_SUBJECT = str(TEST_PATH / 'test_animal_subject.tsv')
TEST_SUBJECT_ERROR = str(TEST_PATH / 'validation_files/test_subject_error.tsv')
TEST_SUBJECT_WARN = str(TEST_PATH / 'validation_files/test_subject_warn.tsv')
TEST_SUBJECT_ALT = str(TEST_PATH / 'test_subject_alt.tsv')
TEST_SUBJECT_SHORT_DUAL = str(TEST_PATH / 'test_subject_short.tsv')
TEST_SUBJECT_SHORT = str(TEST_PATH / 'test_subject_short.tsv')
TEST_METADATA = str(TEST_PATH / 'test_metadata.tsv')
TEST_ANIMAL_METADATA = str(TEST_PATH / 'test_animal_metadata.tsv')
TEST_METADATA_ALT = str(TEST_PATH / 'test_metadata_alt.tsv')
TEST_METADATA_WARN = str(TEST_PATH / 'validation_files/test_metadata_warn.tsv')
TEST_METADATA_SHORT = str(TEST_PATH / 'short_metadata.tsv')
TEST_METADATA_SHORTEST = str(TEST_PATH / 'shortest_metadata.tsv')
UNIQUE_METADATA = str(TEST_PATH / 'unique_metadata.tsv')
TEST_CONFIG_METADATA = str(TEST_PATH / 'test_config_metadata.tsv')
TEST_BARCODES = str(TEST_PATH / 'barcodes.fastq.gz')
TEST_READS = str(TEST_PATH / 'forward_reads.fastq.gz')
TEST_REV_READS = str(TEST_PATH / 'reverse_reads.fastq.gz')
TEST_BARCODES_DUAL = str(TEST_PATH / 'test_S1_L001_I1_001.fastq')
TEST_REV_BARCODES_DUAL = str(TEST_PATH / 'test_S1_L001_I2_001.fastq')
TEST_READS_DUAL = str(TEST_PATH / 'test_S1_L001_R1_001.fastq')
TEST_REV_READS_DUAL = str(TEST_PATH / 'test_S1_L001_R2_001.fastq')
TEST_DEMUXED = str(TEST_PATH / 'test_demuxed.zip')
TEST_GZ = str(TEST_PATH / 'test_archive.tar.gz')
TEST_TOOL = 'tester-5'
TEST_ADD_ALIQUOT = str(TEST_PATH / 'test_add_aliquot.tsv')
TEST_NA_ALIQUOT = str(TEST_PATH / 'test_na_aliquot.tsv')
TEST_ALIQUOT_UPLOAD = str(TEST_PATH / 'test_aliquot_upload.tsv')
TEST_SAMPLE_UPLOAD = str(TEST_PATH / 'test_sample_upload.tsv')
TEST_ADD_SAMPLE = str(TEST_PATH / 'test_add_sample.tsv')
USER_GUIDE = str(TEST_PATH / 'User_Guide.txt')
SUBJECT_TEMPLATE = str(TEST_PATH / 'subject_template.tsv')
SPECIMEN_TEMPLATE = str(TEST_PATH / 'specimen_template.tsv')

# Demultiplexing Qiime Defaults
QIIME_SAMPLE_ID_CATS = ('#SampleID', '#q2:types')
QIIME_FORWARD_BARCODE_CATS = ('BarcodeSequence', 'categorical')
QIIME_REVERSE_BARCODE_CATS = ('BarcodeSequenceR', 'categorical')
FASTQ_FILENAME_TEMPLATE = '{}_S1_L001_R{}_001.fastq.gz'
TEST_FILES = {
    'barcodes': TEST_BARCODES,
    'for_reads': TEST_READS,
    'metadata': TEST_METADATA
}
TEST_CHECKS = {}
for key in TEST_FILES.keys():
    hash1 = hashlib.sha256()
    with open(TEST_FILES[key], 'rb') as f:
        contents = f.read()
    hash1.update(contents)
    TEST_CHECKS[key] = hash1.digest()


##############################
# CONFIGURE DATABASE GLOBALS #
##############################

# The order in which data should be imported to
# ensure the necessary primary keys are created
# before they are referenced as foreign keys
TABLE_ORDER = [
    'Lab',
    'SampleProtocols',
    'RawDataProtocols',
    'ResultsProtocols',
    'ICDCode',
    'IllnessBroadCategory',
    'IllnessCategory',
    'IllnessDetails',
    'Interventions',
    'BodySite',
    'Type',
    'CollectionSite',
    'Study',
    'Experiment',
    'Genotypes',
    'Ethnicity',
    'Subjects',
    'Heights',
    'Weights',
    'Illness',
    'Intervention',
    'Chow',
    'ChowDates',
    'Species',
    'Strain',
    'Facility',
    'Housing',
    'Husbandry',
    'Vendor',
    'AnimalSubjects',
    'HousingDates',
    'SubjectType',
    'StorageLocation',
    'Specimen',
    'Aliquot',
    'SampleProtocol',
    'Sample',
    'RawDataProtocol',
    'RawData',
    'ResultsProtocol',
    'Results',
    'AdditionalMetaData'
]


# Tables that should exist in the subject metadata
SUBJECT_TABLES = {
    'ICDCode',
    'IllnessBroadCategory',
    'IllnessCategory',
    'IllnessDetails',
    'Interventions',
    'Genotypes',
    'Ethnicity',
    'Subjects',
    'SubjectType',
    'Heights',
    'Weights',
    'Illness',
    'Intervention',
    'AdditionalMetaData'
}

ANIMAL_SUBJECT_TABLES = {
    'Chow',
    'ChowDates',
    'Species',
    'Strain',
    'Facility',
    'Housing',
    'HousingDates',
    'Husbandry',
    'Vendor',
    'AnimalSubjects',
    'SubjectType',
    'AdditionalMetaData'
}

# Tables that should exist in the specimen metadata
SPECIMEN_TABLES = ((set(TABLE_ORDER) - SUBJECT_TABLES) - ANIMAL_SUBJECT_TABLES) | {'AdditionalMetaData'}

# MMEDS users are not given direct access to
# these tables as they will contain data that
# is private to other users
PROTECTED_TABLES = [
    'Aliquot',
    'Experiment',
    'Heights',
    'Illness',
    'Intervention',
    'Lab',
    'RawData',
    'RawDataProtocol',
    'Results',
    'ResultsProtocol',
    'Sample',
    'SampleProtocol',
    'Specimen',
    'Study',
    'Subjects',
    'Weights',
    'ChowDates',
    'HousingDates',
    'Husbandry',
    'AnimalSubjects',
    'SubjectType'
]

JUNCTION_TABLES = [
    'Subjects_has_Ethnicity',
    'SubjectType_has_Experiment',
    'Subjects_has_Genotypes'
]

USER_FILES = set(map(
    re.compile,
    [
        '\w*_reads',
        'barcodes',
        'metadata',
        'mapping',
        'visualizations_dir',
        'analysis\w*_summary',
        'analysis\w*_summary_dir'
    ]))

ICD_TABLES = {'IllnessBroadCategory', 'IllnessCategory', 'IllnessDetails'}


# These are the tables that users are given direct access to
PUBLIC_TABLES = set(set(TABLE_ORDER) - set(PROTECTED_TABLES) - set(['AdditionalMetaData', 'ICDCode']))

# These are the columns for each table
TABLE_COLS = {}
ALL_TABLE_COLS = {}
ALL_COLS = []
COL_SIZES = {}

COLUMN_TYPES_SPECIMEN = defaultdict(dict)
COLUMN_TYPES_SUBJECT = defaultdict(dict)
COLUMN_TYPES_ANIMAL_SUBJECT = defaultdict(dict)
COL_TO_TABLE = {}

# Try connecting via the testing setup
if IS_PRODUCTION or TESTING:
    try:
        db = pms.connect(host='localhost',
                         user='root',
                         password='root',
                         db=SQL_DATABASE,
                         max_allowed_packet=2048000000,
                         local_infile=True)
    # Otherwise connect via secured credentials
    except pms.err.OperationalError:
        db = pms.connect(host=sec.SQL_HOST,
                         user=sec.SQL_ADMIN_NAME,
                         password=sec.SQL_ADMIN_PASS,
                         database=sec.SQL_DATABASE,
                         local_infile=True)

    # Get the columns that exist in each table
    c = db.cursor()
    for table in TABLE_ORDER:
        if table == 'ICDCode':
            TABLE_COLS['ICDCode'] = ['ICDCode']
            ALL_COLS += 'ICDCode'
            COL_SIZES['ICDCode'] = ('varchar', 9)
        elif not table == 'AdditionalMetaData':
            c.execute('DESCRIBE ' + table)
            info = c.fetchall()
            results = [x[0] for x in info]
            sizes = [x[1] for x in info]
            for col, size in zip(results, sizes):
                if '(' in size:
                    parts = size.split('(')
                    ctype = parts[0]
                    parsing = parts[1].split(')')[0]
                    if ',' in parsing:
                        cparts = parsing.split(',')
                        csize = (int(cparts[0]), int(cparts[1]))
                    else:
                        csize = int(parsing)
                else:
                    ctype = size
                    csize = 0

                COL_SIZES[col] = (ctype, csize)
            TABLE_COLS[table] = [x for x in results if 'id' not in x]
            ALL_TABLE_COLS[table] = results
            ALL_COLS += results
    c.close()
    TABLE_COLS['AdditionalMetaData'] = []
    DATE_COLS = [col for col in ALL_COLS if 'Date' in col]

    # For use when working with Metadata files
    METADATA_TABLES = set(TABLE_ORDER) - ICD_TABLES
    METADATA_COLS = {}
    for table in METADATA_TABLES:
        METADATA_COLS[table] = TABLE_COLS[table]

    TYPE_MAP = {
        'Text': str,
        'Text: Must be unique': str,
        'Web Address': str,
        'Email': str,
        'Decimal': float,
        'Integer': int,
        'Number': float,
        'Date': Timestamp,
        'Time': Timestamp
    }

    for test_file, col_types, tables in [(TEST_SPECIMEN, COLUMN_TYPES_SPECIMEN, SPECIMEN_TABLES),
                                        (TEST_SUBJECT, COLUMN_TYPES_SUBJECT, SUBJECT_TABLES),
                                        (TEST_ANIMAL_SUBJECT, COLUMN_TYPES_ANIMAL_SUBJECT, ANIMAL_SUBJECT_TABLES)]:
        tdf = read_csv(test_file,
                       sep='\t',
                       header=[0, 1],
                       skiprows=[2, 4],
                       na_filter=False)

        for table in tables:
            try:
                for column in TABLE_COLS[table]:
                    col_type = tdf[table][column].iloc[0]
                    col_types[table][column] = TYPE_MAP[col_type]
                    COL_TO_TABLE[column] = table
            except KeyError:
                if table in ICD_TABLES or table == 'ICDcode':
                    continue
                else:
                    raise

    # Clean up
    del db

    # Create the lists for Sample and Aliquot IDs
    ALIQUOT_ID_COLUMNS = {}
    for col in ['StudyName',
                'SpecimenID',
                'AliquotWeight',
                'AliquotWeightUnit',
                'StorageInstitution',
                'StorageFreezer'
                ]:
        col_type = COLUMN_TYPES_SPECIMEN[COL_TO_TABLE[col]][col]
        ALIQUOT_ID_COLUMNS[col] = col_type

    SAMPLE_ID_COLUMNS = {}
    for col in ['StudyName',
                'AliquotID',
                'SampleDatePerformed',
                'SampleProcessor',
                'SampleProtocolNotes',
                'SampleProtocolID',
                'SampleConditions',
                'SampleTool',
                'SampleToolVersion',
                'SampleWeight',
                'SampleWeightUnit',
                'StorageInstitution',
                'StorageFreezer'
                ]:
        col_type = COLUMN_TYPES_SPECIMEN[COL_TO_TABLE[col]][col]
        SAMPLE_ID_COLUMNS[col] = col_type

    # Map known columns from MIxS
    MMEDS_MAP = {
        'investigation_type': ('Study', 'StudyType'),
        'project_name': ('Study', 'StudyName'),
        'experimental_factor': None,
        'collection_date': ('Specimen', 'CollectionDate'),
        'lat_lon': ('CollectionSite', 'Latitude:Longitude'),
        'geo_loc_name': ('CollectionSite', 'Name'),
        'biome': ('CollectionSite', 'Biome'),
        'feature': ('CollectionSite', 'Feature'),
        'material': ('CollectionSite', 'Material'),
        'env_package': ('CollectionSite', 'Environment'),
        'depth': ('CollectionSite', 'Depth'),
        'lib_reads_seqd': None,
        'target_gene': ('RawDataProtocols', 'TargetGene'),
        'pcr_primers': ('RawDataProtocols', 'Primer'),
        'pcr_cond': ('RawDataProtocols', 'Conditions'),
        'sequencing_meth': ('RawDataProtocols', 'SequencingMethod'),
        'url': ('Study', 'RelevantLinks'),
        'assembly': ('ResultsProtocols', 'Method'),
        'assembly_name': ('ResultsProtocols', 'Name:Version'),
        'isol_growth_condt': ('SampleProtocols', 'Conditions')
    }
    # Map all mmeds columns
    for table in TABLE_COLS:
        for column in TABLE_COLS[table]:
            MMEDS_MAP[column] = (table, column)

    SUBJECT_COLUMNS = {}
    for table in SUBJECT_TABLES:
        cols = TABLE_COLS[table]
        if 'ICDDetails' in cols:
            cols.remove('ICDDetails')
            cols.remove('ICDExtension')
        elif 'ICDCategory' in cols:
            cols.remove('ICDCategory')
        elif 'ICDFirstCharacter' in cols:
            cols.remove('ICDFirstCharacter')
        for col in cols:
            col_type = COLUMN_TYPES_SUBJECT[table][col]
            SUBJECT_COLUMNS[col] = col_type

    MIXS_MAP = {v: k for (k, v) in MMEDS_MAP.items()}


def get_salt(length=10):
    listy = 'abcdefghijklmnopqrzsuvwxyz'
    return ''.join(choice(listy) for i in range(length))
