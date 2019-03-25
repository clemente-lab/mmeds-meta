class MmedsError(Exception):
    """ Base class for errors in this module. """


class MissingUploadError(MmedsError):
    """ Exception for missing uploads. """
    message = 'No data belonging to the user exists for the given access code'


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


class InvalidModuleError(MmedsError):
    """ Exception for errors caused by an invalid module name. """

    def __init__(self, message):
        self.message = message


class NoResultError(MmedsError):
    """ Exception for errors caused by a query returning no result """

    def __init__(self, message):
        self.message = message


class UploadInUseError(MmedsError):
    """ Exception thrown when the requested dataset is currently in use """
    message = 'Requested study is currently unavailable'


class InvalidLoginError(MmedsError):
    """ Exception thrown when the provided login credentials don't match a known user """
    message = 'No user exists with the provided username and password'
