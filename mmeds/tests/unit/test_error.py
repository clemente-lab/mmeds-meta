from unittest import TestCase
import mmeds.error as err


class ErrorTests(TestCase):
    """ Iterate through all the errors in MMEDs, creating an instance of each to ensure they work """
    def test_all(self):
        for error, err_cls in err.__dict__.items():
            if isinstance(err_cls, type) and issubclass(err_cls, err.MmedsError):
                try:
                    # Some don't take arguments so that situation is handled
                    try:
                        err_cls("Some text goes here")
                    except TypeError:
                        err_cls()
                except err.MmedsError:
                    pass
