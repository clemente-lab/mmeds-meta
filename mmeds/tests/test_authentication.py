import mmeds.authentication as auth


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
    assert auth.validate_password(test_username2, test_password2, testing=True)
    assert not auth.validate_password(test_username2, test_password1, testing=True)
    assert not auth.validate_password(bad_username, test_password2, testing=True)


def test_c_check_password():
    results4 = auth.check_password(bad_password3, bad_password3)
    assert 'upper and lower' in results4

    results1 = auth.check_password(bad_password1, bad_password2)
    assert 'do not match' in results1

    results2 = auth.check_password(bad_password1, bad_password1)
    assert 'at least one number' in results2

    results3 = auth.check_password(bad_password2, bad_password2)
    assert 'following symbols' in results3

    results5 = auth.check_password(bad_password4, bad_password4)
    assert 'longer than 10' in results5

    assert '' == auth.check_password(test_password1, test_password1)


def test_d_check_username():
    assert auth.check_username(test_username3, testing=True) is None
    assert 'Error' in auth.check_username(bad_username, testing=True)


def test_e_get_email():
    assert test_email2 == auth.get_email(test_username2, testing=True)
    assert not auth.get_email(test_username3, testing=True)


def test_f_change_password():
    assert auth.validate_password(test_username2, test_password2, testing=True)
    assert auth.change_password(test_username2, test_password3, testing=True) is None
    assert auth.validate_password(test_username2, test_password3, testing=True)


def test_g_remove_user():
    """ Test the add_user function """
    assert not auth.remove_user(test_username2, testing=True)
