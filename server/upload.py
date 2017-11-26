import os
import os.path

import cherrypy
from cherrypy.lib import static
from mmeds.mmeds import check_metadata

localDir = os.path.dirname(__file__)
absDir = os.path.join(os.getcwd(), localDir)

UPLOADED_FP = 'uploaded_file'


class FileUpload(object):

    @cherrypy.expose
    def index(self):
        return open('./index.html')

    @cherrypy.expose
    def upload(self, myFile):

        # Write the data to a new file stored on the server
        nf = open(UPLOADED_FP, 'wb')
        while True:
            data = myFile.file.read(8192)
            nf.write(data)
            if not data:
                break
        nf.close()

        result = check_metadata(UPLOADED_FP)

        # Get the html for the upload page
        with open('./upload.html', 'r') as f:
            uploaded_output = f.read()
        return uploaded_output.format(filename=myFile.filename, output=result.decode('utf-8'))

    @cherrypy.expose
    def corrections(self):
        return open('./' + UPLOADED_FP + '.html')

    @cherrypy.expose
    def log(self):
        path = os.path.join(absDir, UPLOADED_FP + '.log')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

    @cherrypy.expose
    def download(self):
        path = os.path.join(absDir, UPLOADED_FP + '_corrected.txt')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))


mmeds_conf = os.path.join(os.path.dirname(__file__), 'cherry.conf')

if __name__ == '__main__':
    cherrypy.quickstart(FileUpload(), config=mmeds_conf)
