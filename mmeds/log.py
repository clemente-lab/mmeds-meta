import logging
import mmeds.config as fig
import multiprocessing_logging as mpl
from multiprocessing import current_process

loggers = {}


class MMEDSLog():
    global loggers
    mpl.install_mp_handler()

    def __init__(self, name):
        if loggers.get(name):
            self.logger = loggers.get(name)
        else:
            self.logger = logging.getLogger('Error')
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            fh = logging.FileHandler(fig.MMEDS_LOG)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)

            ch = logging.StreamHandler()
            ch.setLevel(logging.ERROR)
            ch.setFormatter(formatter)

            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
            loggers[name] = self.logger

    def startLog(self, name):
        self.logger = logging.getLogger(name)

    def debug(self, message):
        self.logger.debug(str(current_process()) + ' - ' + message)

    def error(self, message):
        self.logger.error(str(current_process()) + ' - ' + message)
