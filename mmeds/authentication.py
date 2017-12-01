import hashlib
import pickle

from random import choice
from string import printable

LOGIN_FILE = '../server/data/login_info'


def get_salt(strength=10):
    """ Get a randomly generated string for salting passwords. """
    return ''.join(choice(printable) for i in range(strength))


def validate_password(username, password):
    """ Validate the user and their password """

    # Load the users
    with open(LOGIN_FILE, 'rb') as f:
        login_info = pickle.load(f)

    salt = login_info[username][1]

    # Hash the password
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
    password_hash = sha256.digest()

    return username in login_info and login_info[username][0] == password_hash


def add_user(username, password):
    """ Adds a user to the file containing login info. """

    # Hash the password
    salt = get_salt()
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
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
        login_info[username] = [password_hash, salt]

    # Write the dictionary
    with open(LOGIN_FILE, 'wb') as f:
        pickle.dump(login_info, f)
