import hashlib

from string import ascii_uppercase, ascii_lowercase
from mmeds import database
from mmeds.config import STORAGE_DIR, get_salt

LOGIN_FILE = '../server/data/login_info'


def validate_password(username, password):
    """ Validate the user and their password """

    db = database.Database(STORAGE_DIR)
    # Get the values from the user table
    try:
        hashed_password, salt =\
            db.get_col_values_from_table('password, salt',
                                         'mmeds.user where username = "{}"'.format(username))[0]
    # An index error means that the username did not exist
    except IndexError:
        return False

    # Hash the password
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
    password_hash = sha256.hexdigest()

    # Check that it matches the stored hash of the password
    return hashed_password == password_hash


def add_user(username, password):
    """ Adds a user to the file containing login info. """

    # Hash the password
    salt = get_salt()
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
    password_hash = sha256.hexdigest()
    db = database.Database(STORAGE_DIR)
    db.add_user(username, password_hash, salt)


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

    # Check the username does not contain invalid characters
    invalid_chars = set('\'\"\\/ ;,!@#$%^&*()|[{}]`~')
    if set(username).intersection(invalid_chars):
        return 'Error: Username contains invalid characters.'

    # Check the username has not already been used
    db = database.Database(STORAGE_DIR)

    # Get all existing usernames
    results = db.get_col_values_from_table('username', 'user')
    used_names = [x[0] for x in results]
    if username in used_names:
        return 'Error: Username is already taken.'
    return
