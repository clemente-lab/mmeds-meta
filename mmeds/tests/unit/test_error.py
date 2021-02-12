from unittest import TestCase
import mmeds.error as err


class ErrorTests(TestCase):
    def test_all(self):
        for error, err_cls in err.__dict__.items():
            ty = type(err_cls)
            if isinstance(err_cls, type) and issubclass(err_cls, err.MmedsError):
                try:
                    try:
                        err_instance = err_cls("Some text goes here")
                    except TypeError:
                        err_instance = err_cls()
                except err.MmedsError:
                    pass
