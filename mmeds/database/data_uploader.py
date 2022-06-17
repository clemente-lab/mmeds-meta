import warnings

import mmeds.secrets as sec
import mmeds.config as fig
import mongoengine as men
import pymysql as pms

from datetime import datetime
from pathlib import Path
from multiprocessing import Process
from mmeds.database.documents import MMEDSDoc
from mmeds.logging import Logger
from mmeds.util import (send_email, create_local_copy)


class DataUploader(Process):
    """
    This class handles the processing and uploading of fastq sequencing run files into the MySQL database.
    """
    def __init__(self, owner, reads_type, barcodes_type, sequencing_run_name,
                 data_files, public, testing, access_code=None):
        warnings.simplefilter('ignore')
        super().__init__()
        Logger.debug('DataUploader created with params')
        Logger.debug({
            'owner': owner,
            'reads_type': reads_type,
            'barcodes_type': barcodes_type,
            'sequencing_run_name': sequencing_run_name,
            'data_files': data_files,
            'public': public,
            'testing': testing
        })

        self.owner = owner
        self.testing = testing
        self.reads_type = reads_type
        self.barcodes_type = barcodes_type
        self.sequencing_run_name = sequencing_run_name
        self.public = public
        self.datafiles = data_files
        self.created = datetime.now()

        # If testing connect to test server
        if testing:
            self.db = pms.connect(host='localhost',
                                  user='root',
                                  password=sec.TEST_ROOT_PASS,
                                  database=fig.SQL_DATABASE,
                                  autocommit=True,
                                  local_infile=True)
            # Connect to the mongo server
            self.mongo = men.connect(db='test',
                                     port=27017,
                                     host='127.0.0.1')
        # Otherwise connect to the deployment server
        else:
            self.db = pms.connect(host=sec.SQL_HOST,
                                  user=sec.SQL_ADMIN_NAME,
                                  password=sec.SQL_ADMIN_PASS,
                                  database=sec.SQL_DATABASE,
                                  autocommit=True,
                                  local_infile=True)
            self.mongo = men.connect(db=sec.MONGO_DATABASE,
                                     username=sec.MONGO_ADMIN_NAME,
                                     password=sec.MONGO_ADMIN_PASS,
                                     port=sec.MONGO_PORT,
                                     authentication_source=sec.MONGO_DATABASE,
                                     host=sec.MONGO_HOST)

        if access_code is None:
            self.access_code = fig.get_salt(50)
            # Ensure a unique access code
            while list(MMEDSDoc.objects(access_code=self.access_code)):
                self.access_code = fig.get_salt(50)
        else:
            self.access_code = access_code

        # Create the document
        self.mdata = MMEDSDoc(created=datetime.utcnow(),
                              last_accessed=datetime.utcnow(),
                              testing=self.testing,
                              doc_type='sequencing_run',
                              reads_type=self.reads_type,
                              barcodes_type=self.barcodes_type,
                              study_name=self.sequencing_run_name,
                              access_code=self.access_code,
                              owner=self.owner,
                              public=self.public)

        self.mdata.save()

        count = 0
        new_dir = fig.SEQUENCING_DIR / ('{}_{}_{}'.format(self.owner, self.sequencing_run_name, count))

        while new_dir.is_dir():
            count += 1
            new_dir = fig.SEQUENCING_DIR / ('{}_{}_{}'.format(self.owner, self.sequencing_run_name, count))
        new_dir.mkdir()

        self.path = Path(new_dir) / 'database_files'
        MMEDSDoc.objects.timeout(False)

    def get_info(self):
        """ Method to return a dictionary of relevant info for the process log """
        info = {
            'created': self.created,
            'type': 'upload-run',
            'owner': self.owner,
            'pid': self.pid,
            'name': self.name,
            'exitcode': self.exitcode
        }
        return info

    def run(self):
        """
        Thread that handles the upload of sequencing run files.
        """
        self.mdata.update(is_alive=True)
        self.mdata.save()
        Logger.debug('Handling upload for sequencing run {} for user {}'.format(self.sequencing_run_name, self.owner))

        # If the owner is None set user_id to 0
        if self.owner is None:
            self.user_id = 0
            self.email = fig.MMEDS_EMAIL
        # Otherwise get the user id for the owner from the database
        else:
            sql = 'SELECT user_id, email FROM user WHERE user.username=%(uname)s'
            cursor = self.db.cursor()
            cursor.execute(sql, {'uname': self.owner})
            result = cursor.fetchone()
            cursor.close()
            # Ensure the user exists
            if result is None:
                raise NoResultError('No account exists with the provided username and email.')
            self.user_id = int(result[0])
            self.email = result[1]

        # If the metadata is to be made public overwrite the user_id
        if self.public:
            self.user_id = 1
        self.check_file = fig.DATABASE_DIR / 'last_check.dat'

        if not self.path.is_dir():
            self.path.mkdir()
        self.mdata.update(path=str(self.path.parent))
        self.mdata.save()

        # Create a copy of the Data files
        datafile_copies = {key: create_local_copy(Path(filepath).read_bytes(),
                                                  f"{Path(filepath).name}", self.path.parent, False)
                           for key, filepath in self.datafiles.items()
                           if filepath is not None}

        # Create sequencing run directory file
        with open(self.path.parent / fig.SEQUENCING_DIRECTORY_FILE, "wt") as f:
            for key, filepath in self.datafiles.items():
                adjusted = key
                if key == 'for_reads':
                    adjusted = 'forward'
                elif key == 'rev_reads':
                    adjusted = 'reverse'
                f.write(f"{adjusted}: {Path(filepath).name}\n")

        self.mongo_import(**datafile_copies)

        # Send the confirmation email
        send_email(self.email, self.owner, message='upload-run', run=self.sequencing_run_name,
                   code=self.access_code, testing=self.testing)
        # Update the doc to reflect the successful upload
        self.mdata.update(is_alive=False, exit_code=0)
        self.mdata.save()
        return 0

    def mongo_import(self, **kwargs):
        """ Imports additional columns into the NoSQL database. """
        self.mdata.files.update(kwargs)
        self.mdata.update(email=self.email, path=str(self.path.parent))
        self.mdata.save()
