import pytest
import mmeds.authentication as auth


test_username1 = 'username'
test_password1 = 'Password1@Password'
test_username2 = 'usernamee'
test_password2 = 'Password1@Passworde'
bad_password1 = 'PasswordPassword'
bad_password2 = 'Password1Password'
bad_password3 = 'password1@password'
bad_password4 = 'Passwor1@'


def test_add_user():
    """ Test the add_user function """
    assert not auth.add_user(test_username2, test_password2)


def test_validate_password():
    assert auth.validate_password(test_username1, test_password1)


def test_check_password():
    results1 = auth.check_password(bad_password1, bad_password2)
    assert 'do not match' in results1

    results2 = auth.check_password(bad_password1, bad_password1)
    assert 'at least one number' in results2

    results3 = auth.check_password(bad_password2, bad_password2)
    assert 'following symbols' in results3

    results4 = auth.check_password(bad_password3, bad_password3)
    assert 'upper and lower' in results4

    results5 = auth.check_password(bad_password4, bad_password4)
    assert 'longer than 10' in results5

    assert '' == auth.check_password(test_password1, test_password1)
