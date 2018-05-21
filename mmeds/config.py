from random import choice
from string import digits, ascii_uppercase, ascii_lowercase


def get_salt(strength=10):
    """ Get a randomly generated string for salting passwords. """
    return ''.join(choice(digits + ascii_uppercase + ascii_lowercase) for i in range(strength))


CONFIG = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'log.error_file': 'site.log',
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': '../server/data/cert.pem',
        'server.ssl_private_key': '../server/data/key.pem',
        'tools.secureheaders.on': True,
        'tools.sessions.on': True,
        'tools.sessions.secure': True,
        'tools.sessions.httponly': True,
        'request.scheme': 'https'
    },
    '/favicon.ico': {
        'tools.staticfile.filename': '/home/david/Work/mmeds-meta/server/favicon.ico',
        'tools.staticfile.on': True,
    },
    '/protected/area': {
        'tools.auth_digest': True,
        'tools.auth_digest.realm': 'localhost',
        'tools.auth_digest.key': 'a565c2714791cfb',
    }
}

UPLOADED_FP = 'uploaded_file'
ERROR_FP = 'error_log.csv'
STORAGE_DIR = 'data/'
SECURITY_TOKEN = 'some_security_token'
