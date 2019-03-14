from cherrypy._cpdispatch import Dispatcher
from mmeds.util import log


class DownloadHandler(Dispatcher):
    """ Handle all download requests made to the server. """
    def __call__(self, path_info):
        """ Parse the given url and pass the user to the right page. """
        log(path_info)
        return Dispatcher.__call__(self, path_info)
