from secrets import choice
from string import digits, ascii_uppercase, ascii_lowercase
from pathlib import Path
import pymysql as pms
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
SQL_DATABASE = 'mmeds_data1'
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
        'tools.auth_digest.realm': '0.0.0.0',
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
TEST_METADATA = str(TEST_PATH / 'qiime_metadata.csv')
TEST_METADATA_FAIL = str(TEST_PATH / 'test_qiime_metadata.csv')
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
    'CollectionSite',
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
    'CollectionSite',
    'Experiment',
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

# These are the columns for each table
TABLE_COLS = {}
ALL_COLS = []
with pms.connect('localhost', 'root', '', SQL_DATABASE, max_allowed_packet=2048000000, local_infile=True) as db:
    for table in TABLE_ORDER:
        if not table == 'AdditionalMetaData':
            db.execute('DESCRIBE ' + table)
            results = [x[0] for x in db.fetchall() if 'id' not in x[0]]
            TABLE_COLS[table] = results
            ALL_COLS += results
    TABLE_COLS['AdditionalMetaData'] = []

MMEDS_MAP = {
    'investigation_type': ('Study', 'StudyType'),
    'project_name': ('Study', 'StudyName'),
    'experimental_factor': None,
    'collection_date': ('Specimen', 'CollectionDate'),
    'lat_lon': ('CollectionSite', '##PARSE##'),
    'geo_loc_name': None,
    'biome': ('CollectionSite', 'Biome'),
    'feature': ('CollectionSite', 'Feature'),
    'material': ('CollectionSite', 'Material'),
    'env_package': None,
    'depth': ('CollectionSite', 'Depth'),
    'ammonium': None,
    'chlorophyll': None,
    'density': None,
    'nitrate': None,
    'org_carb': None,
    'org_nitro': None,
    'organism_count': None,
    'oxy_stat_samp': None,
    'phosphate': None,
    'salinity': None,
    'silicate': None,
    'temp': None,
    'tot_depth_water_col': None,
    'rel_to_oxygen': None,
    'samp_collect_device': None,
    'samp_mat_process': None,
    'samp_size': None,
    'nucl_acid_ext': None,
    'nucl_acid_amp': None,
    'lib_reads_seqd': None,
    'target_gene': None,
    'subfragment': None,
    'pcr_primers': None,
    'mid': None,
    'adapter': None,
    'pcr_cond': None,
    'sequencing_meth': ('RawDataProtocols', 'RawDataProtocolscol'),
    'url': ('Study', 'RelevantLinks')
}

MIXS_MAP = {v: k for k, v in MMEDS_MAP.items()}


def get_salt(length=10, numeric=False):
    """ Get a randomly generated string for salting passwords. """
    if numeric:
        listy = digits
    else:
        listy = digits + ascii_uppercase + ascii_lowercase
    return ''.join(choice(listy) for i in range(length))
