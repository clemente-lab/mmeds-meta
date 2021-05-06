from socket import gethostname

SECURITY_TOKEN = 'res5423dsd2asd'
DIGEST_KEY = 'c675a1913791cf4'
SQL_ADMIN_NAME = 'mmedsadmin'
SQL_ADMIN_PASS = 'sQvA9UXTPD'
SQL_USER_NAME = 'mmedsusers'
SQL_USER_PASS = 'e2r7wVfrFe'
SQL_HOST = 'data1'
SQL_DATABASE = 'mmeds_data1'
MONGO_PORT = 27017
MONGO_HOST = 'web01'
MONGO_ADMIN_NAME = 'mmedsadmin'
MONGO_ADMIN_PASS = 'T7t5GYU9ts'
MONGO_DATABASE = 'mmeds_web01'
if gethostname() == 'web01':
    SERVER_HOST = '10.95.46.35'
else:
    SERVER_HOST = '127.0.0.1'
SERVER_PORT = 52953
TEST_EMAIL_PASS = "_]%*',Gy3+@j"
EMAIL_PASS = 'iph$6\{B[MDe@!'
TEST_PASS = 'testpassL33TG@m3r'
TEST_USER_PASS = 'password'
TEST_ROOT_PASS = ''
AUTH_KEY = b'F1ndTh3W@tch3r'
WATCHER_PORT = 52953
