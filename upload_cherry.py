import os
import os.path

import cherrypy
from cherrypy.lib import static
import pymongo

localDir = os.path.dirname(__file__)
absDir = os.path.join(os.getcwd(), localDir)


class FileDemo(object):
    filename = None

    @cherrypy.expose
    def index(self):
        return open('./index.html')

    @cherrypy.expose
    def upload(self, myFile):
        with open('./file_info.html') as f:
            out = f.read()
        size = 0
        filename = 'uploaded_file'
        nf = open(filename, 'wb')
        while True:
            data = myFile.file.read(8192)
            nf.write(data)
            if not data:
                break
            size += len(data)
        nf.close()
        self.filename = myFile.filename
        return out % (size, myFile.filename, myFile.content_type)

    @cherrypy.expose
    def download(self):
        path = os.path.join(absDir, self.filename)
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))


tutconf = os.path.join(os.path.dirname(__file__), 'cherry.conf')

if __name__ == '__main__':
    cherrypy.quickstart(FileDemo(), config=tutconf)
