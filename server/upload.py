import os
import os.path

import cherrypy
from cherrypy.lib import static
from mmeds.mmeds import check_metadata
from mmeds.config import CONFIG
from mmeds.authentication import validate_password

localDir = os.path.dirname(__file__)
absDir = os.path.join(os.getcwd(), localDir)

UPLOADED_FP = 'uploaded_file'


class MMEDSserver(object):

    @cherrypy.expose
    def index(self):
        """ Home page of the application """
        return open('./login.html')

    @cherrypy.expose
    def upload(self, myFile):
        """ The page returned after a file is uploaded. """
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
        """ Page containing the marked up metadata as an html file """
        return open('./' + UPLOADED_FP + '.html')

    @cherrypy.expose
    def login(self, username, password):
        """
        Opens the page to upload files if the user has been authenticated.
        Otherwise returns to the login page with an error message.
        """
        if validate_password(username, password):
            return open('./index.html')
        else:
            return open('./login_error.html')

    @cherrypy.expose
    def log(self):
        """ Allows the user to download a log file """
        path = os.path.join(absDir, UPLOADED_FP + '.log')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

    @cherrypy.expose
    def download(self):
        """ Allows the user to download the correct metadata file. """
        path = os.path.join(absDir, UPLOADED_FP + '_corrected.txt')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))


if __name__ == '__main__':
    cherrypy.quickstart(MMEDSserver(), config=CONFIG)
