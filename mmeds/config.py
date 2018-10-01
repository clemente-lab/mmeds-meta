from secrets import choice
from string import digits, ascii_uppercase, ascii_lowercase
from pathlib import Path
import hashlib
# Add some notes here
# Add some more notes here

UPLOADED_FP = 'uploaded_file'
ERROR_FP = 'error_log.csv'

# The path changes depening on where this is being called
# So that it will work with testing and the server
HTML_DIR = Path('../html/').resolve()
if not HTML_DIR.is_dir():
    HTML_DIR = Path('./html/').resolve()
STORAGE_DIR = Path('./data').resolve()
if not STORAGE_DIR.is_dir():
    STORAGE_DIR = Path('../server/data').resolve()
if not STORAGE_DIR.is_dir():
    STORAGE_DIR = Path('./server/data').resolve()

SECURITY_TOKEN = 'some_security_token'
CONTACT_EMAIL = 'david.wallach@mssm.edu'
MMEDS_EMAIL = 'donotreply.mmed.server@gmail.com'
PORT = 8080


CONFIG = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'server.socket_port': PORT,
        'log.error_file': str(STORAGE_DIR.parent / 'site.log'),
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': str(STORAGE_DIR / 'cert.pem'),
        'server.ssl_private_key': str(STORAGE_DIR / 'key.pem'),
        'request.scheme': 'https',
        'secureheaders.on': True,
        'tools.sessions.on': True,
        'tools.sessions.secure': True,
        'tools.sessions.httponly': True,
        'tools.staticdir.root': Path().cwd().parent,
    },
    # Content in this directory will be made directly
    # available on the web server
    '/CSS': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': 'CSS'
    },
    # This sets up the https security
    '/protected/area': {
        'tools.auth_digest': True,
        'tools.auth_digest.realm': 'localhost',
        'tools.auth_digest.key': 'a565c2714791cfb',
    }
}


###################
##### Testing #####
###################

TEST_PATH = Path('./data_files/').resolve()
if not TEST_PATH.is_dir():
    TEST_PATH = Path('../data_files/').resolve()

TEST_PASS = 'testpass'
TEST_USER = 'testuser'
TEST_USER_0 = 'testuser0'
TEST_EMAIL = 'mmeds.tester@gmail.com'
TEST_EMAIL_PASS = 'testmmeds1234'
TEST_CODE = 'asdfasdfasdfasdf'
TEST_DIR = STORAGE_DIR / 'test_dir'
TEST_DIR_0 = STORAGE_DIR / 'test_dir0'
TEST_METADATA = str(TEST_PATH / 'test_qiime_metadata.csv')
TEST_METADATA_FAIL = str(TEST_PATH / 'qiime_metadata.csv')
TEST_METADATA_FAIL_0 = str(TEST_PATH / 'test0_metadata.csv')
TEST_METADATA_VALID = str(TEST_PATH / 'validate_qiime_metadata.csv')
TEST_BARCODES = str(TEST_PATH / 'barcodes.fastq.gz')
TEST_READS = str(TEST_PATH / 'forward_reads.fastq.gz')
TEST_TOOL = 'tester-1'
TEST_FILES = {
    'reads': TEST_READS,
    'barcodes': TEST_BARCODES,
    'metadata': TEST_METADATA
}
TEST_CHECKS = {}
for key in TEST_FILES.keys():
    hash1 = hashlib.md5()
    with open(TEST_FILES[key], 'rb') as f:
        contents = f.read()
    hash1.update(contents)
    TEST_CHECKS[key] = hash1.digest()


# The order in which data should be imported to
# ensure the necessary primary keys are created
# before they are referenced as foreign keys
TABLE_ORDER = [
    'Lab',
    'Study',
    'Experiment',
    'Genotypes',
    'Ethnicity',
    'Illnesses',
    'Interventions',
    'SampleProtocols',
    'RawDataProtocols',
    'ResultsProtocols',
    'Type',
    'BodySite',
    'Location',
    'Subjects',
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
    'Lab',
    'Study',
    'Experiment',
    'Location',
    'Subjects',
    'Illness',
    'Intervention',
    'Specimen',
    'Aliquot',
    'SampleProtocol',
    'Sample',
    'RawDataProtocol',
    'RawData',
    'ResultsProtocol',
    'Results'
]

USER_FILES = set([
    'reads',
    'barcodes',
    'metadata',
    'mapping',
    'visualizations_dir'
])

# These are the tables that users are given direct access to
PUBLIC_TABLES = set(TABLE_ORDER) - set(PROTECTED_TABLES) - set(['AdditionalMetaData'])


def get_salt(length=10, numeric=False):
    """ Get a randomly generated string for salting passwords. """
    if numeric:
        listy = digits
    else:
        listy = digits + ascii_uppercase + ascii_lowercase
    return ''.join(choice(listy) for i in range(length))
