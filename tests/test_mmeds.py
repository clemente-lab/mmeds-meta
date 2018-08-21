from mmeds import mmeds


def test_is_numeric():
    assert mmeds.is_numeric('4.5') is True
    assert mmeds.is_numeric('r.5') is False
