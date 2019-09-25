import logging
import mmeds.config as fig
import multiprocessing_logging as mpl
from multiprocessing import current_process

loggers = {}
mpl.install_mp_handler()


class MMEDSLog():
    # Used by multiple processes to ensure that multiple loggers with the same name aren't created
    global loggers

    def __init__(self, name, testing=False):
        if loggers.get(name):
            self.logger = loggers.get(name)
        else:
            self.logger = logging.getLogger('Error')
            if 'error' in name.lower():
                self.logger.setLevel(logging.ERROR)
            elif 'info' in name.lower():
                self.logger.setLevel(logging.INFO)
            elif 'debug' in name.lower():
                self.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s -%(levelname)s - %(message)s')
            if 'SQL' in name:
                fh = logging.FileHandler(fig.SQL_LOG)
            else:
                fh = logging.FileHandler(fig.MMEDS_LOG)
            if testing:
                fh.setLevel(logging.DEBUG)
            else:
                fh.setLevel(logging.INFO)

            fh.setFormatter(formatter)

            ch = logging.StreamHandler()
            ch.setLevel(logging.ERROR)
            ch.setFormatter(formatter)

            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
            loggers[name] = self.logger

    def debug(self, message):
        self.logger.debug(str(current_process()) + ' - ' + message)

    def error(self, message):
        self.logger.error(str(current_process()) + ' - ' + message)

    def info(self, message):
        self.logger.info(str(current_process()) + ' - ' + message)
