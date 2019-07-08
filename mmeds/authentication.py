import hashlib
from string import ascii_uppercase, ascii_lowercase
from mmeds.database import Database
from mmeds.config import STORAGE_DIR, get_salt
from mmeds.util import send_email, log
from mmeds.error import NoResultError, InvalidLoginError, InvalidPasswordErrors, InvalidUsernameError


def add_user(username, password, email, privilege_level=0, testing=False):
    """ Adds a user to the file containing login info. """

    # Hash the password
    salt = get_salt()
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
    password_hash = sha256.hexdigest()
    with Database(testing=testing) as db:
        db.add_user(username, password_hash, salt, email, privilege_level)


def remove_user(username, testing=False):
    """ Removes a user from the user sql table. """
    with Database(testing=testing) as db:
        db.clear_user_data(username)
        db.remove_user(username)


def validate_password(username, password, testing=False):
    """ Validate the user and their password """

    with Database(testing=testing) as db:
        # Get the values from the user table
        try:
            hashed_password, salt = db.get_hash_and_salt(username)
        # An index error means that the username did not exist
        except NoResultError:
            log('No user with name: {}'.format(username))
            raise InvalidLoginError()

    # Hash the password
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
    password_hash = sha256.hexdigest()

    # Check that it matches the stored hash of the password
    if not hashed_password == password_hash:
        log('No user with name: {} and password_hash: {}'.format(username, password_hash))
        raise InvalidLoginError()


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
    if len(password1) <= 10:
        errors.append('Error: Passwords must be longer than 10 characters.')

    if errors:
        raise InvalidPasswordErrors(errors)


def check_username(username, testing=False):
    """ Perform checks to ensure the username is valid. """

    # Don't allow public as a username
    if username.lower() == 'public':
        raise InvalidUsernameError('Error: Username is invalid.')

    # Check the username does not contain invalid characters
    invalid_chars = set('\'\"\\/ ;,!@#$%^&*()|[{}]`~')
    if set(username).intersection(invalid_chars):
        raise InvalidUsernameError('Error: Username contains invalid characters.')

    # Check the username has not already been used
    with Database(STORAGE_DIR, testing=testing) as db:
        # Get all existing usernames
        used_names = db.get_all_usernames()
    if username in used_names:
        raise InvalidUsernameError('Error: Username is already taken.')


def reset_password(username, email, testing=False):
    """ Reset the password for the current user. """
    # Create a new password
    password = get_salt(20)
    salt = get_salt()
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
    password_hash = sha256.hexdigest()

    with Database(STORAGE_DIR, user='root', owner=username, testing=testing) as db:
        if not db.email == email:
            raise NoResultError('No account exists with the provided username and email.')
        result = db.change_password(password_hash, salt)
    send_email(email, username, password=password, message='reset', testing=testing)
    return result


def change_password(username, password, testing=False):
    """ Reset the password for the current user. """
    # Create a new password
    salt = get_salt()
    salted = password + salt
    sha256 = hashlib.sha256()
    sha256.update(salted.encode('utf-8'))
    password_hash = sha256.hexdigest()

    with Database(STORAGE_DIR, user='root', owner=username, testing=testing) as db:
        # Check the email matches the one on file
        db.change_password(password_hash, salt)
        send_email(db.get_email(username), username, password=password, message='change', testing=testing)


def get_email(username, testing=False):
    """ Retrieve the email for the specified user account. """
    with Database(testing=testing) as db:
        # Get the values from the user table
        return db.get_email(username)


def check_privileges(username, testing=False):
    """ Retrieve the email for the specified user account. """
    with Database(testing=testing) as db:
        # Get the values from the user table
        return bool(db.get_privileges(username))
