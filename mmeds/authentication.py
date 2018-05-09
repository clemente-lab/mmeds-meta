import hashlib
import pickle

from random import choice
from string import printable, ascii_uppercase, ascii_lowercase

LOGIN_FILE = '../server/data/login_info'


def get_salt(strength=10):
    """ Get a randomly generated string for salting passwords. """
    return ''.join(choice(printable) for i in range(strength))


def validate_password(username, password):
    """ Validate the user and their password """

    # Load the users
    with open(LOGIN_FILE, 'rb') as f:
        login_info = pickle.load(f)

    if username not in login_info:
        return False

    salt = login_info[username][1]

    # Hash the password
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
    password_hash = sha256.digest()

    return login_info[username][0] == password_hash


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
        login_info[username] = [password_hash, salt, []]

    # Write the dictionary
    with open(LOGIN_FILE, 'wb') as f:
        pickle.dump(login_info, f)


def check_password(password1, password2):
    """ Perform checks to make sure passwords are strong enough. """
    nums = set('0123456789')
    syms = set('!@#$%^&*~`-_+=')
    pas = set(password1)
    errors = []

    if not password1 == password2:
        errors.append('Error: Passwords do not match')
    if not pas.intersection(nums):
        errors.append('Error: Passwords must contain at least one number.')
    if not pas.intersection(syms):
        errors.append('Error: Passwords must contain at least one of the following symbols ' + str(syms) + ' .')
    if not (pas.intersection(set(ascii_uppercase)) and pas.intersection(set(ascii_lowercase))):
        errors.append('Error: Passwords must contain a mix of upper and lower case characters.')
    if len(password1) < 10:
        errors.append('Error: Passwords must be longer than 10 characters.')

    return '<br \>'.join(errors)


def check_username(username):
    """ Perform checks to ensure the username is valid. """

    invalid_chars = set('\'\"\\/ ;,!@#$%^&*()|[{}]`~')
    if set(username).intersection(invalid_chars):
        return 'Error: Username contains invalid characters.'
    try:
        with open(LOGIN_FILE, 'rb') as f:
            login_info = pickle.load(f)
        users = login_info.keys()
        if username in users:
            return 'Error: Username is already taken.'
    # If there are no users the username can't be a repeat
    except EOFError:
        return

    return


def add_studies_to_user(username, tables):
    """
    Adds the specified tables to the list of tables the user
    should have access to.
    """
    # Load the dictionary
    try:
        with open(LOGIN_FILE, 'rb') as f:
            login_info = pickle.load(f)
    # If it's the first entry
    except EOFError as e:
        raise e

    # Add the tables to be allowed
    login_info[username][2] += tables

    # Write the dictionary
    with open(LOGIN_FILE, 'wb') as f:
        pickle.dump(login_info, f)

    return login_info[username][2]
