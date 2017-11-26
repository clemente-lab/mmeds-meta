USERS = {'jon': 'secret'}


def validate_password(username, password):
    """ Validate the user and their password """
    return username in USERS and USERS[username] == password
