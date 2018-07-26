class MmedsError(Exception):
    """ Base class for errors in this module. """
    pass


class MissingUploadError(MmedsError):
    """ Exception for missing uploads. """

    def __init__(self, expression, message):
        self.expresssion = expression
        self.message = message
