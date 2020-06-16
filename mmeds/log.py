import logging
import mmeds.config as fig
if fig.TESTING:
    from multiprocessing import current_process
else:
    from multiprocessing.dummy import current_process

loggers = {}


class MMEDSLog():
    # Used by multiple processes to ensure that multiple loggers with the same name aren't created
    global loggers

    def __init__(self, name, testing=True):
        # If the logger already exists grab it
        if loggers.get(name):
            self.logger = loggers.get(name)
        else:
            self.logger = logging.getLogger(name)
            if 'error' in name.lower():
                self.logger.setLevel(logging.ERROR)
            elif 'info' in name.lower() or 'sql' in name.lower():
                self.logger.setLevel(logging.INFO)
            elif 'debug' in name.lower():
                self.logger.setLevel(logging.DEBUG)

            if 'SQL' in name:
                fh = logging.FileHandler(fig.SQL_LOG)
            else:
                fh = logging.FileHandler(fig.MMEDS_LOG)

            if testing:
                fh.setLevel(logging.DEBUG)
            else:
                fh.setLevel(logging.INFO)

            self.logger.setLevel(logging.DEBUG)
            fh.setLevel(logging.DEBUG)

            #  logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
            #                          datefmt='%Y-%m-%d:%H:%M:%S',
            #                          level=logging.DEBUG)

            fmt_str = 'h[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
            formatter = logging.Formatter(fmt_str, '%m-%d %H:%M:%S')
            fh.setFormatter(formatter)

            ch = logging.StreamHandler()
            ch.setLevel(logging.ERROR)
            ch.setFormatter(formatter)

            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
            loggers[name] = self.logger

    def debug(self, message):
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug(str(current_process()) + ' - ' + message)

    def error(self, message):
        self.logger.setLevel(logging.ERROR)
        self.logger.error(str(current_process()) + ' - ' + message)

    def info(self, message):
        self.logger.setLevel(logging.INFO)
        self.logger.info(str(current_process()) + ' - ' + message)
