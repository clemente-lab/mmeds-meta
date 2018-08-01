from secrets import choice
from string import digits, ascii_uppercase, ascii_lowercase
from smtplib import SMTP
from email.message import EmailMessage
from pathlib import Path
from cherrypy.lib.sessions import FileSession

CONFIG = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'log.error_file': 'site.log',
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': '../server/data/cert.pem',
        'server.ssl_private_key': '../server/data/key.pem',
        'request.scheme': 'https',
        'secureheaders.on': True,
        'tools.sessions.on': True,
        #'tools.sessions.storage_class': FileSession,
        #'tools.sessions.storage_path': Path.cwd() / 'session',
        'tools.sessions.secure': True,
        'tools.sessions.httponly': True,
        'tools.staticdir.root': Path().cwd().parent,
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

UPLOADED_FP = 'uploaded_file'
ERROR_FP = 'error_log.csv'
STORAGE_DIR = 'data'
SECURITY_TOKEN = 'some_security_token'
CONTACT_EMAIL = 'david.wallach@mssm.edu'
MMEDS_EMAIL = 'donotreply.mmed.server@gmail.com'


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
    msg['Subject'] = 'New data uploaded to mmeds database'
    if message == 'upload':
        body = 'Hello {},\nthe user {} uploaded data to the mmeds database server.\n'.format(toaddr, user) +\
               'In order to gain access to this data without the password to\n{} you must provide '.format(user) +\
               'the following access code:\n{}\n\nBest,\nMmeds Team\n\n'.format(kwargs['code']) +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(CONTACT_EMAIL)
    elif message == 'reset':
        body = 'Hello {},\nYour password has been reset.\n'.format(toaddr) +\
               'The new password is:\n{}\n\nBest,\nMmeds Team\n\n'.format(kwargs['password']) +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(CONTACT_EMAIL)
    elif message == 'change':
        body = 'Hello {},\nYour password has been changed.\n'.format(toaddr) +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(CONTACT_EMAIL)
    elif message == 'analysis':
        body = 'Hello {},\nYour requested analysis on study {} is complete.\n'.format(toaddr, kwargs['study_name']) +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(CONTACT_EMAIL)

    msg.set_content(body)

    server = SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(MMEDS_EMAIL, 'mmeds_server')
    server.send_message(msg)
    server.quit()
