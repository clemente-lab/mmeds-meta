class MmedsError(Exception):
    """ Base class for errors in this module. """
    pass


class MissingUploadError(MmedsError):
    """ Exception for missing uploads. """

    def __init__(self, message):
        self.message = message


class TableAccessError(MmedsError):
    """ Exception for missing uploads. """

    def __init__(self, message):
        self.message = message


class MetaDataError(MmedsError):
    """ Exception for missing uploads. """

    def __init__(self, message):
        self.message = message


class AnalysisError(MmedsError):
    """ Exception for errors during analysis. """

    def __init__(self, message):
        self.message = message
