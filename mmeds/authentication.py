import hashlib
import pickle

LOGIN_FILE = '../server/data/login_info'


def validate_password(username, password):
    """ Validate the user and their password """

    # Load the users
    with open(LOGIN_FILE, 'rb') as f:
        login_info = pickle.load(f)

    # Hash the password
    sha256 = hashlib.sha256()
    sha256.update(password.encode('utf-8'))
    password_hash = sha256.digest()

    return username in login_info and login_info[username] == password_hash


def add_user(username, password):
    """ Adds a user to the file containing login info. """

    # Hash the password
    sha256 = hashlib.sha256()
    sha256.update(password.encode('utf-8'))
    password_hash = sha256.digest()

    # Load the dictionary
    try:
        with open(LOGIN_FILE, 'rb') as f:
            login_info = pickle.load(f)
    # If it's the first entry
    except EOFError:
        login_info = {}

    # Add the user
    if username not in login_info.keys():
        login_info[username] = password_hash

    # Write the dictionary
    with open(LOGIN_FILE, 'wb') as f:
        pickle.dump(login_info, f)
