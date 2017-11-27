import os
import os.path

import cherrypy
from cherrypy.lib import static
from mmeds.mmeds import check_metadata, insert_error
from mmeds.config import CONFIG
from mmeds.authentication import validate_password

localDir = os.path.dirname(__file__)
absDir = os.path.join(os.getcwd(), localDir)

UPLOADED_FP = 'uploaded_file'
UPLOADED_DIR = 'uploaded_data/'


class MMEDSserver(object):

    @cherrypy.expose
    def index(self):
        """ Home page of the application """
        return open('../html/index.html')

    @cherrypy.expose
    def validate(self, myFile):
        """ The page returned after a file is uploaded. """

        valid_extensions = ['txt', 'csv', 'tsv']
        file_extension = myFile.filename.split('.')[-1]
        if file_extension not in valid_extensions:
            with open('../html/upload.html') as f:
                page = f.read()
            return insert_error(page, 14, 'Error: ' + file_extension + ' is not a valid filetype.')
        # Write the data to a new file stored on the server
        nf = open(UPLOADED_DIR + UPLOADED_FP, 'wb')
        while True:
            data = myFile.file.read(8192)
            nf.write(data)
            if not data:
                break
        nf.close()

        result = check_metadata(UPLOADED_FP, UPLOADED_DIR)

        # Get the html for the upload page
        with open('../html/validate.html', 'r') as f:
            uploaded_output = f.read()

        return uploaded_output.format(filename=myFile.filename, output=result.decode('utf-8'))

    @cherrypy.expose
    def login(self, username, password):
        """
        Opens the page to upload files if the user has been authenticated.
        Otherwise returns to the login page with an error message.
        """
        if validate_password(username, password):
            return open('../html/upload.html')
        else:
            with open('../html/index.html') as f:
                page = f.read()
            return insert_error(page, 17, 'Error: Invalid username or password.')

    # View files
    @cherrypy.expose
    def view_corrections(self):
        """ Page containing the marked up metadata as an html file """
        return open(UPLOADED_DIR + UPLOADED_FP + '.html')

    # Download links
    @cherrypy.expose
    def download_log(self):
        """ Allows the user to download a log file """
        path = os.path.join(absDir, UPLOADED_DIR + UPLOADED_FP + '.log')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))

    @cherrypy.expose
    def download_corrected(self):
        """ Allows the user to download the correct metadata file. """
        path = os.path.join(absDir, UPLOADED_DIR + UPLOADED_FP + '_corrected.txt')
        return static.serve_file(path, 'application/x-download',
                                 'attachment', os.path.basename(path))


if __name__ == '__main__':
    cherrypy.quickstart(MMEDSserver(), config=CONFIG)
