import logging
import mmeds.config as fig
import multiprocessing_logging as mpl
from multiprocessing import current_process


class MMEDSLog():

    def __init__(self):
        self.logger = logging.getLogger('MMEDSLogger')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh = logging.FileHandler(fig.MMEDS_LOG)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)

        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        mpl.install_mp_handler()

    def startLog(self, name):
        self.logger = logging.getLogger(name)

    def debug(self, message):
        self.logger.debug(str(current_process()) + ' - ' + message)

    def error(self, message):
        self.logger.error(str(current_process()) + ' - ' + message)
