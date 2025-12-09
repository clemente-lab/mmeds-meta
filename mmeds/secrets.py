from socket import gethostname

SECURITY_TOKEN = ''
DIGEST_KEY = ''
SQL_ADMIN_NAME = ''
SQL_ADMIN_PASS = ''
SQL_USER_NAME = 'mmedsusers'
SQL_USER_PASS = ''
SQL_HOST = ''
SQL_DATABASE = 'mmeds_data1'
MONGO_PORT = 27017
MONGO_HOST = ''
MONGO_ADMIN_NAME = ''
MONGO_ADMIN_PASS = ''
MONGO_DATABASE = 'mmeds_web01'
if gethostname() == 'web01':
    SERVER_HOST = '10.95.46.35'
else:
    SERVER_HOST = '127.0.0.1'
SERVER_PORT = 52953
TEST_EMAIL_PASS = ''
EMAIL_PASS = ''
TEST_PASS = 'testpassL33TG@m3r'
TEST_USER_PASS = 'password'
TEST_ROOT_PASS = 'root'
REUPLOAD_PASS = 'r3Up10@D'
AUTH_KEY = b'F1ndTh3W@tch3r'
WATCHER_PORT = 52953
