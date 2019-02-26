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


class LoggedOutError(MmedsError):
    """ Exception for errors caused by not being logged in"""

    def __init__(self, message):
        self.message = message


class InvalidConfigError(MmedsError):
    """ Exception for errors caused by selecting invalid columns in the config file"""

    def __init__(self, message):
        self.message = message


class InvalidSQLError(MmedsError):
    """ Exception for errors caused by invalid characters in a SQL query"""

    def __init__(self, message):
        self.message = message


class NoResultError(MmedsError):
    """ Exception for errors caused by a query returning no result """

    def __init__(self, message):
        self.message = message
