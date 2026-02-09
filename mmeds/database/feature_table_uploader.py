import warnings

import mmeds.secrets as sec
import mmeds.config as fig
import mmeds.database.documents as docs
import mongoengine as men
import pymysql as pms

from datetime import datetime
from pathlib import Path
from multiprocessing import Process
from mmeds.error import NoResultError
from mmeds.logging import Logger
from mmeds.util import (send_email, create_local_copy)


class FeatureTableUploader(Process):
    """
    This class handles the processing and uploading of observation matrix tables
    """
    def __init__(self, access_code, owner, studies, table_name, table_type, table_file, public, testing):
        warnings.simplefilter('ignore')
        super().__init__()
        Logger.debug('FeatureTableUploader created with params')
        Logger.debug({
            'owner': owner,
            'table_name': table_name,
            'table_type': table_type,
            'table_file': table_file,
            'public': public,
            'testing': testing
        })

        self.created = datetime.now()
        self.access_code = access_code
        self.owner = owner
        self.testing = testing
        self.table_name = table_name
        self.public = public

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

        # Create the document
        self.doc = docs.FeatureTableDoc(created=datetime.utcnow(),
                                        last_accessed=datetime.utcnow(),
                                        testing=self.testing,
                                        doc_type=docs.DocType.FEATURE_TABLE,
                                        access_code=self.access_code,
                                        table_name=self.table_name,
                                        table_type=self.table_type,
                                        studies=self.studies,
                                        owner=self.owner,
                                        public=self.public,
                                        latest_version=True)
        self.doc.save()

    def get_info(self):
        """ Method to return a dictionary of relevant info for the process log """
        info = {
            'created': self.created,
            'type': 'upload-feature-table',
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
        self.doc.update(is_alive=True)
        self.doc.save()
        Logger.debug('Handling upload for feature table {} for user {}'.format(self.table_name, self.owner))

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

        if not self.path.is_dir():
            self.path.mkdir()
        self.doc.update(path=str(self.path.parent))
        self.doc.save()

        self.mongo_import(self.table_file)

        # Send the confirmation email
        send_email(self.email, self.owner, message='upload-feature_table', study=self.studies[0],
                   table_name=self.table_name, code=self.access_code, testing=self.testing)
        # Update the doc to reflect the successful upload
        self.doc.update(is_alive=False, exit_code=0)
        self.doc.save()
        return 0

    def mongo_import(self, table_file):
        """ Imports additional columns into the NoSQL database. """
        self.doc.table = men.GridFSProxy()
        with open(table_file, "rb") as f:
            self.doc.table.put(f, content_type="text/plain")

        self.doc.update(email=self.email, path=str(self.path.parent))
        self.doc.save()
