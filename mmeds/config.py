from pathlib import Path
from random import choice
from pandas import read_csv
import pymysql as pms
import mmeds.secrets as sec
import mmeds.html as html
import mmeds.test_files as test_files
import mmeds.resources as resources
import mmeds.CSS as css
import mmeds
import hashlib
import os
import re


############################
# CONFIGURE SERVER GLOBALS #
############################

UPLOADED_FP = 'uploaded_file'
ERROR_FP = 'error_log.tsv'

ROOT = Path(mmeds.__file__).parent.resolve()
HTML_DIR = Path(html.__file__).parent.resolve()
CSS_DIR = Path(css.__file__).parent.resolve()
STORAGE_DIR = Path(resources.__file__).parent.resolve()
if os.environ.get('MMEDS'):
    DATABASE_DIR = Path(os.environ.get('MMEDS')) / 'mmeds_server_data'
else:
    DATABASE_DIR = Path().home() / 'mmeds_server_data'
MODULE_ROOT = DATABASE_DIR.parent / '.modules/modulefiles'

if not os.path.exists(DATABASE_DIR):
    os.mkdir(DATABASE_DIR)

JOB_TEMPLATE = STORAGE_DIR / 'job_template.lsf'
MMEDS_LOG = DATABASE_DIR / 'mmeds_log.txt'
CONFIG_PARAMETERS = [
    'sampling_depth',
    'metadata',
    'taxa_levels',
    'abundance_threshold',
    'font_size'
]
CONTACT_EMAIL = 'david.wallach@mssm.edu'
MMEDS_EMAIL = 'donotreply.mmed.server@gmail.com'
SQL_DATABASE = 'mmeds_data1'


# Configuration for the CherryPy server
CONFIG = {
    'global': {
        'server.socket_host': sec.SERVER_HOST,
        'server.socket_port': sec.SERVER_PORT,
        'server.socket_timeout': 1000000000,
        'server.max_request_body_size': 10000000000,
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': str(STORAGE_DIR / 'cert.pem'),
        'server.ssl_private_key': str(STORAGE_DIR / 'key.pem'),
        'log.error_file': str(DATABASE_DIR / 'site.log'),
        'request.scheme': 'https',
        'secureheaders.on': True,
        'tools.sessions.secure': True,
        'tools.sessions.on': True,
        'tools.sessions.httponly': True,
        'tools.sessions.timeout': 15
    },
    # Content in this directory will be made directly
    # available on the web server
    '/CSS': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': str(CSS_DIR)
    },
    # This sets up the https security
    '/protected/area': {
        'tools.auth_digest': True,
        'tools.auth_digest.realm': sec.SERVER_HOST,
        'tools.auth_digest.key': sec.DIGEST_KEY,
    }
}


##########################
# CONFIGURE TEST GLOBALS #
##########################

TEST_PATH = Path(test_files.__file__).parent.resolve()
TEST_DIR = DATABASE_DIR / 'test_dir'
if not os.path.exists(TEST_DIR):
    os.mkdir(TEST_DIR)
TEST_DIR_0 = DATABASE_DIR / 'test_dir0'
if not os.path.exists(TEST_DIR_0):
    os.mkdir(TEST_DIR_0)

TEST_PASS = 'testpass'
TEST_USER_PASS = 'password'
TEST_ROOT_PASS = ''
TEST_USER = 'testuser'
SERVER_USER = 'serveruser'
TEST_USER_0 = 'testuser0'
TEST_EMAIL = 'mmeds.tester@gmail.com'
TEST_EMAIL_PASS = 'testmmeds1234'
TEST_CODE = 'singlereads'
TEST_CODE_PAIRED = 'pairedreads'
TEST_CODE_DEMUX = 'demuxedreads'
TEST_MIXS = str(TEST_PATH / 'test_MIxS.tsv')
TEST_MIXS_MMEDS = str(TEST_PATH / 'MIxS_metadata.tsv')
TEST_CONFIG = str(TEST_PATH / 'test_config_file.txt')
TEST_CONFIG_1 = str(TEST_PATH / 'test_config_file_fail1.txt')
TEST_CONFIG_2 = str(TEST_PATH / 'test_config_file_fail2.txt')
TEST_CONFIG_3 = str(TEST_PATH / 'test_config_file_fail3.txt')
TEST_CONFIG_ALL = str(TEST_PATH / 'test_config_all.txt')
TEST_MAPPING = str(TEST_PATH / 'qiime_mapping_file.tsv')
TEST_METADATA = str(TEST_PATH / 'test_metadata.tsv')
UNIQUE_METADATA = str(TEST_PATH / 'unique_metadata.tsv')
TEST_CONFIG_METADATA = str(TEST_PATH / 'test_config_metadata.tsv')
TEST_METADATA_1 = str(TEST_PATH / 'test_metadata_1.tsv')
TEST_METADATA_SHORT = str(TEST_PATH / 'short_metadata.tsv')
TEST_METADATA_FAIL = str(TEST_PATH / 'test_metadata_fail.tsv')

TEST_METADATA_FAIL_0 = str(TEST_PATH / 'test_metadata_fail_0.tsv')
TEST_METADATA_VALID = str(TEST_PATH / 'test_metadata_valid.tsv')
TEST_BARCODES = str(TEST_PATH / 'barcodes.fastq.gz')
TEST_READS = str(TEST_PATH / 'forward_reads.fastq.gz')
TEST_REV_READS = str(TEST_PATH / 'forward_reads.fastq.gz')
TEST_DEMUXED = str(TEST_PATH / 'test_demuxed.zip')
TEST_TOOL = 'tester-5'
TEST_FILES = {
    'reads': TEST_READS,
    'barcodes': TEST_BARCODES,
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
    'Interventions',
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
    'Weights'
]

JUNCTION_TABLES = [
    'Subjects_has_Ethnicity',
    'Subjects_has_Experiment',
    'Subjects_has_Genotypes'
]

USER_FILES = set(map(
    re.compile,
    [
        'reads',
        'barcodes',
        'metadata',
        'mapping',
        'visualizations_dir',
        'analysis*_summary',
        'analysis*_summary_dir'
    ]))

ICD_TABLES = set(['IllnessBroadCategory', 'IllnessCategory', 'IllnessDetails'])


# These are the tables that users are given direct access to
PUBLIC_TABLES = set(set(TABLE_ORDER) - set(PROTECTED_TABLES) - set(['AdditionalMetaData', 'ICDCode']))

# These are the columns for each table
TABLE_COLS = {}
ALL_COLS = []

# Try connecting via the testing setup
try:
    db = pms.connect('localhost',
                     'root',
                     '',
                     SQL_DATABASE,
                     max_allowed_packet=2048000000,
                     local_infile=True)
# Otherwise connect via secured credentials
except pms.err.OperationalError:
    db = pms.connect(host=sec.SQL_HOST,
                     user=sec.SQL_ADMIN_NAME,
                     password=sec.SQL_ADMIN_PASS,
                     database=sec.SQL_DATABASE,
                     local_infile=True)
c = db.cursor()
for table in TABLE_ORDER:
    if table == 'ICDCode':
        TABLE_COLS['ICDCode'] = ['ICDCode']
        ALL_COLS += 'ICDCode'
    elif not table == 'AdditionalMetaData':
        c.execute('DESCRIBE ' + table)
        results = [x[0] for x in c.fetchall() if 'id' not in x[0]]
        TABLE_COLS[table] = results
        ALL_COLS += results
TABLE_COLS['AdditionalMetaData'] = []

# For use when working with Metadata files
METADATA_TABLES = set(TABLE_ORDER) - ICD_TABLES
METADATA_COLS = {}
for table in METADATA_TABLES:
    METADATA_COLS[table] = TABLE_COLS[table]


COLUMN_TYPES = {}
tdf = read_csv(TEST_METADATA,
               sep='\t',
               header=[0, 1],
               skiprows=[2, 4],
               na_filter=False)

for table in TABLE_COLS:
    # Temporary solution
    try:
        COLUMN_TYPES[table] = {}
        for column in TABLE_COLS[table]:
            col_type = tdf[table][column].iloc[0]
            if 'Text' in col_type:
                COLUMN_TYPES[table][column] = 'str'
            elif 'Number' in col_type:
                COLUMN_TYPES[table][column] = 'float'
            elif 'Date' in col_type:
                COLUMN_TYPES[table][column] = 'datetime64'
    except KeyError:
        continue

# Clean up
del db

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

MIXS_MAP = {v: k for (k, v) in MMEDS_MAP.items()}


def get_salt(length=10):
    listy = 'abcdefghijklmnopqrzsuvwxyz'
    return ''.join(choice(listy) for i in range(length))


############################
# CONFIGURE SERVER GLOBALS #
############################


# Each page returns a tuple
# (<Path to the page>, <Should the header and topbar be loaded>)
HTML_PAGES = {
    'index': (HTML_DIR / 'index.html', False),
    'welcome': (HTML_DIR / 'welcome.html', True),
    'analysis_select_tool': (HTML_DIR / 'analysis_select_tool.html', True),
    'auth_change_password': (HTML_DIR / 'auth_change_password.html', True),
    'auth_sign_up_page': (HTML_DIR / 'auth_sign_up_page.html', False),
    'download_study_files': (HTML_DIR / 'download_study_files.html', True),
    'download_select_file': (HTML_DIR / 'download_select_file.html', True),
    'upload_data_files': (HTML_DIR / 'upload_data_files.html', True),
    'upload_metadata_error': (HTML_DIR / 'upload_metadata_error.html', True),
    'upload_metadata_files': (HTML_DIR / 'upload_metadata_files.html', True),
    'upload_files_page': (HTML_DIR / 'upload_files_page.html', True),
    'upload_metadata_warning': (HTML_DIR / 'upload_metadata_warning.html', True)
}
