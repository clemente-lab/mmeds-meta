import logging
import inspect

from logging.config import dictConfig

__author__ = "Matthew Stapylton"
__copyright__ = "Copyright 2020, The Clemente Lab"
__credits__ = ["David Wallach", "Matthew Stapylton", "Jose Clemente"]
__license__ = "GPL"
__maintainer__ = "David Wallach"
__email__ = "david.wallach@mssm.edu"


def format_log_message(log_message):
    """ Performs formatting of lists and dicts passed in as log messages """
    if isinstance(log_message, list):
        log_message = '[ ' + ',\n'.join([str(x) for x in log_message]) + ' ]'
    elif isinstance(log_message, dict):
        joined_message = ['{}: {}'.format(key, value) for key, value in log_message.items()]
        log_message = ('{ ' + ',\n'.join(joined_message) + ' }').replace('{', '{{').replace('}', '}}')
    return '{} - {}'.format(inspect.stack()[2][3], log_message)


class Logger:

    def __init__(self, log_config):
        """
        Initializes python's logger object
        Requires the log_config section of ensemble_yaml.config
        """
        dictConfig(log_config)

    def _log(log_level, log_message, *log_args):
        """
        Logs the string passed to this method.
        log_args is are optional arguments that are formatted to the log message.
        """

        # Retrieve the logger.
        # TODO: Logic to handle multiple loggers.
        logger = logging.getLogger('mmeds_logger')
        try:
            if logger is None:
                print('No logger initialized')
            elif log_level.lower() == 'info':
                logger.info(log_message.format(*log_args))
            elif log_level.lower() == 'debug':
                logger.debug(log_message.format(*log_args))
            elif log_level.lower() == 'warn':
                logger.warning(log_message.format(*log_args))
            elif log_level.lower() == 'error':
                logger.error(log_message.format(*log_args))
            else:
                logger.error('Incorrect logging level')
        except KeyError:
            breakpoint()

    @staticmethod
    def info(log_message, *log_args):
        """Logs a message at info level"""
        return Logger._log('info', format_log_message(log_message), *log_args)

    @staticmethod
    def debug(log_message, *log_args):
        """Logs a message at debug level"""
        return Logger._log('debug', format_log_message(log_message), *log_args)

    @staticmethod
    def warn(log_message, *log_args):
        """Logs a message at warning level"""
        return Logger._log('warn', format_log_message(log_message), *log_args)

    @staticmethod
    def error(log_message, *log_args):
        """Logs a message at error level"""
        return Logger._log('error', format_log_message(log_message), *log_args)
