from mmeds.log import MMEDSLog
from multiprocessing import current_process


class MmedsError(Exception):
    """ Base class for errors in this module. """
    def __init__(self):
        log = MMEDSLog('Info')
        log.error('A {} was raised. Message {}'.format(type(self), self.message))


class MissingUploadError(MmedsError):
    """ Exception for missing uploads. """

    def __init__(self):
        self.message = 'No data belonging to the user exists for the given access code'
        super().__init__()


class TableAccessError(MmedsError):
    """ Exception for missing uploads. """

    def __init__(self, message):
        self.message = message
        super().__init__()


class MetaDataError(MmedsError):
    """ Exception for missing uploads. """

    def __init__(self, message):
        self.message = message
        super().__init__()


class AnalysisError(MmedsError):
    """ Exception for errors during analysis. """

    def __init__(self, message):
        self.message = message
        super().__init__()


class LoggedOutError(MmedsError):
    """ Exception for errors caused by not being logged in"""

    def __init__(self, message):
        self.message = message
        super().__init__()


class InvalidConfigError(MmedsError):
    """ Exception for errors caused by selecting invalid columns in the config file"""

    def __init__(self, message):
        self.message = message
        super().__init__()


class InvalidSQLError(MmedsError):
    """ Exception for errors caused by invalid characters in a SQL query"""

    def __init__(self, message):
        self.message = message
        super().__init__()


class InvalidModuleError(MmedsError):
    """ Exception for errors caused by an invalid module name. """

    def __init__(self, message):
        self.message = message
        super().__init__()


class NoResultError(MmedsError):
    """ Exception for errors caused by a query returning no result """

    def __init__(self, message):
        self.message = message
        super().__init__()


class InvalidUsernameError(MmedsError):
    """ Exception for errors caused by a query returning no result """

    def __init__(self, message):
        self.message = message
        super().__init__()


class InvalidPasswordErrors(MmedsError):
    """ Exception for errors caused by a query returning no result """

    def __init__(self, message):
        self.message = ','.join(message)
        super().__init__()


class UploadInUseError(MmedsError):
    """ Exception thrown when the requested dataset is currently in use """
    def __init__(self):
        self.message = 'Requested study is currently unavailable'
        super().__init__()


class InvalidLoginError(MmedsError):
    """ Exception thrown when the provided login credentials don't match a known user """
    def __init__(self):
        self.message = 'No user exists with the provided username and password'
        super().__init__()


class InvalidMetaDataFileError(MmedsError):
    """ Exception for errors parsing the metadata file """

    def __init__(self, message):
        self.message = message
        super().__init__()


class MissingFileError(MmedsError):
    """ Exception for missing file errors """

    def __init__(self, message):
        self.message = message
        super().__init__()
