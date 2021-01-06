import logging
import inspect

from logging.config import dictConfig

__author__ = "Matthew Stapylton"
__copyright__ = "Copyright 2020, The Clemente Lab"
__credits__ = ["David Wallach", "Matthew Stapylton", "Jose Clemente"]
__license__ = "GPL"
__maintainer__ = "David Wallach"
__email__ = "david.wallach@mssm.edu"


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

    @staticmethod
    def info(log_message, *log_args):
        """Logs a message at info level"""
        log_message = str(inspect.stack()[2][3]) + ' - ' + log_message
        return Logger._log('info', log_message, *log_args)

    @staticmethod
    def debug(log_message, *log_args):
        """Logs a message at debug level"""
        log_message = str(inspect.stack()[2][3]) + ' - ' + log_message
        return Logger._log('debug', log_message, *log_args)

    @staticmethod
    def warn(log_message, *log_args):
        """Logs a message at warning level"""
        log_message = str(inspect.stack()[2][3]) + ' - ' + log_message
        return Logger._log('warn', log_message, *log_args)

    @staticmethod
    def error(log_message, *log_args):
        """Logs a message at error level"""
        log_message = str(inspect.stack()[2][3]) + ' - ' + log_message
        return Logger._log('error', log_message, *log_args)
