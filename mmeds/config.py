from secrets import choice
from string import digits, ascii_uppercase, ascii_lowercase
from smtplib import SMTP
from email.message import EmailMessage
from pathlib import Path
from cherrypy.lib.sessions import FileSession, RamSession
# Add some notes here
# Add some more notes here

UPLOADED_FP = 'uploaded_file'
ERROR_FP = 'error_log.csv'
STORAGE_DIR = Path('./data').resolve()
if not STORAGE_DIR.is_dir():
    STORAGE_DIR = Path('../server/data').resolve()
if not STORAGE_DIR.is_dir():
    STORAGE_DIR = Path('./server/data').resolve()

# The path changes depening on where this is being called
# So that it will work with testing and the server
HTML_DIR = Path('../html/').resolve()
if not HTML_DIR.is_dir():
    HTML_DIR = Path('./html/').resolve()
SECURITY_TOKEN = 'some_security_token'
CONTACT_EMAIL = 'david.wallach@mssm.edu'
MMEDS_EMAIL = 'donotreply.mmed.server@gmail.com'


CONFIG = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'log.error_file': str(STORAGE_DIR.parent / 'site.log'),
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': str(STORAGE_DIR / 'cert.pem'),
        'server.ssl_private_key': str(STORAGE_DIR / 'key.pem'),
        'request.scheme': 'https',
        'secureheaders.on': True,
        'tools.sessions.on': True,
        'tools.sessions.secure': True,
        'tools.sessions.httponly': True,
        'tools.staticdir.root': Path().cwd().parent,  # Change this for different install locations
        'request.scheme': 'https'
    },
    '/CSS': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': 'CSS'
    },
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
TEST_PASS = 'testpass'
TEST_USER = 'testuser'
TEST_EMAIL = 'd.s.t.wallach@gmail.com'
TEST_CODE = 'asdfasdfasdfasdf'
TEST_DIR = STORAGE_DIR / 'test_dir'
TEST_METADATA = str(TEST_PATH / 'qiime_metadata.csv')
TEST_BARCODES = str(TEST_PATH / 'barcodes.fastq.gz')
TEST_READS = str(TEST_PATH / 'read.fastq.gz')
TEST_FILES = [
    'reads',
    'barcodes',
    'metadata'
]

TEST_CONFIG = {
    'global': {
        'log.error_file': str(STORAGE_DIR.parent / 'site.log'),
        'tools.sessions.on': True,
        'tools.sessions.name': 'cp_session',
#       'tools.sessions.storage_class': RamSession,
#       'tools.sessions.storage_path': STORAGE_DIR / 'session',
#       'tools.sessions.timeout': (1.0 / 60),
#       'tools.sessions.clean_freq': (1.0 / 60)
    },
    '/CSS': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': 'CSS'
    },
    '/protected/area': {
        'tools.auth_digest': True,
        'tools.auth_digest.realm': 'localhost',
        'tools.auth_digest.key': 'a565c2714791cfb',
    }
}


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

PUBLIC_TABLES = set(TABLE_ORDER) - set(PROTECTED_TABLES) - set(['AdditionalMetaData'])


def get_salt(length=10, numeric=False):
    """ Get a randomly generated string for salting passwords. """
    if numeric:
        listy = digits
    else:
        listy = digits + ascii_uppercase + ascii_lowercase
    return ''.join(choice(listy) for i in range(length))


def send_email(toaddr, user, message='upload', **kwargs):
    """ Sends a confirmation email to addess containing user and code. """
    msg = EmailMessage()
    msg['From'] = MMEDS_EMAIL
    msg['To'] = toaddr
    if message == 'upload':
        body = 'Hello {},\nthe user {} uploaded data to the mmeds database server.\n'.format(toaddr, user) +\
               'In order to gain access to this data without the password to\n{} you must provide '.format(user) +\
               'the following access code:\n{}\n\nBest,\nMmeds Team\n\n'.format(kwargs['code']) +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(CONTACT_EMAIL)
        msg['Subject'] = 'New data uploaded to mmeds database'
    elif message == 'reset':
        body = 'Hello {},\nYour password has been reset.\n'.format(toaddr) +\
               'The new password is:\n{}\n\nBest,\nMmeds Team\n\n'.format(kwargs['password']) +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(CONTACT_EMAIL)
        msg['Subject'] = 'Password Reset'
    elif message == 'change':
        body = 'Hello {},\nYour password has been changed.\n'.format(toaddr) +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(CONTACT_EMAIL)
        msg['Subject'] = 'Password Change'
    elif message == 'analysis':
        body = 'Hello {},\nYour requested {} analysis on study {} is complete.\n'.format(kwargs['analysis_type'],
                                                                                         toaddr,
                                                                                         kwargs['study_name']) +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(CONTACT_EMAIL)
        msg['Subject'] = 'Analysis Complete'

    msg.set_content(body)

    server = SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(MMEDS_EMAIL, 'mmeds_server')
    server.send_message(msg)
    server.quit()
