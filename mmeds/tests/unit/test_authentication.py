import mmeds.authentication as auth

from mmeds.error import NoResultError, InvalidLoginError, InvalidPasswordErrors, InvalidUsernameError
from pytest import raises


test_username1 = 'username'
test_password1 = 'Password1@Password'
test_username2 = 'usernamee'
test_password2 = 'Password1@Passworde'
test_username3 = 'usernameee'
test_password3 = 'Password2@Passworde'
test_email2 = 'some@email.com'
bad_username = 'baduser@@'
bad_password1 = 'passwordpassword'
bad_password2 = 'password1password'
bad_password3 = 'password1@password'
bad_password4 = 'Passwor1@'


def test_a_add_user():
    """ Test the add_user function """
    assert auth.add_user(test_username2, test_password2, test_email2, testing=True) is None


def test_b_validate_password():
    # Shouldn't raise an error
    auth.validate_password(test_username2, test_password2, testing=True) is None

    with raises(InvalidLoginError):
        auth.validate_password(test_username2, test_password1, testing=True)
    with raises(InvalidLoginError):
        auth.validate_password(bad_username, test_password2, testing=True)


def test_c_check_password():
    with raises(InvalidPasswordErrors) as e:
        auth.check_password(bad_password3, bad_password3)
        assert 'upper and lower' in e.message[0]

    with raises(InvalidPasswordErrors) as e:
        auth.check_password(bad_password1, bad_password2)
        assert 'do not match' in e.message[0]

    with raises(InvalidPasswordErrors) as e:
        auth.check_password(bad_password1, bad_password1)
        assert 'at least one number' in e.message[0]

    with raises(InvalidPasswordErrors) as e:
        auth.check_password(bad_password2, bad_password2)
        assert 'following symbols' in e.message[0]

    with raises(InvalidPasswordErrors) as e:
        auth.check_password(bad_password4, bad_password4)
        assert 'longer than 10' in e.message[0]

    auth.check_password(test_password1, test_password1)


def test_d_check_username():
    auth.check_username(test_username3, testing=True)
    with raises(InvalidUsernameError) as e:
        auth.check_username(bad_username, testing=True)
        assert 'Error' in e.message


def test_e_get_email():
    assert test_email2 == auth.get_email(test_username2, testing=True)
    with raises(NoResultError):
        auth.get_email(test_username3, testing=True)


def test_f_change_password():
    auth.validate_password(test_username2, test_password2, testing=True)
    assert auth.change_password(test_username2, test_password3, testing=True) is None
    auth.validate_password(test_username2, test_password3, testing=True)
    with raises(NoResultError):
        assert auth.change_password('public', test_password3, testing=True) is None
    with raises(NoResultError):
        assert auth.change_password('rando', test_password3, testing=True) is None


def test_g_remove_user():
    """ Test the add_user function """
    assert not auth.remove_user(test_username2, testing=True)
