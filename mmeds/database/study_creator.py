import warnings

import mmeds.secrets as sec
import mmeds.config as fig
import mongoengine as men
import pymysql as pms

from datetime import datetime
from pathlib import Path
from collections import defaultdict
from multiprocessing import Process
from mmeds.error import NoResultError
from mmeds.util import send_email
import mmeds.database.documents as doc
from mmeds.logging import Logger


class StudyCreator(Process):
    """
    This class handles the creation of a study object as a MongoDB document and a location on disk
    """
    def __init__(self, access_code, study_name, subject_type, owner, meta_study, public, testing):
        """
        Connect to the specified database.
        Initialize variables for this session.
        ---------------------------------------
        :access_code: A string. To be used for creating MongoDB document
        :study_name: A string. Name for the study
        :subject_type: A string. One of 'human', 'animal', 'mixed'
        :owner: A string. The mmeds user account performing upload
        :meta_study: A boolean. Whether or not the study will be made of previous uploads
        :public: A boolean. Whether to make study visible to all users
        :testing: A boolean. Changes the connection parameters for testing
        """
        warnings.simplefilter('ignore')
        super().__init__()
        Logger.debug('StudyCreator created with params')
        Logger.debug({
            'study_name': study_name,
            'subject_type': subject_type,
            'owner': owner,
            'meta_study': meta_study,
            'public': public,
            'testing': testing
        })

        self.created = datetime.now()
        self.IDs = defaultdict(dict)
        self.access_code = access_code
        self.study_name = study_name
        self.subject_type = subject_type
        self.owner = owner
        self.testing = testing
        self.meta_study = meta_study
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

        count = 0
        new_dir = fig.STUDIES_DIR / ('{}_{}_{}'.format(self.owner, self.study_name, count))
        while new_dir.is_dir():
            count += 1
            new_dir = fig.STUDIES_DIR / ('{}_{}_{}'.format(self.owner, self.study_name, count))
        new_dir.mkdir()

        self.path = Path(new_dir)
        doc.MMEDSDoc.objects.timeout(False)

        # Create the MongoDB document
        self.study = doc.StudyDoc(created=datetime.utcnow(),
                                  last_accessed=datetime.utcnow(),
                                  public=self.public,
                                  testing=self.testing,
                                  owner=self.owner,
                                  access_code=self.access_code,
                                  doc_type=doc.DocType.STUDY,
                                  study_name=self.study_name,
                                  path=self.path)
        self.study.save()

    def get_info(self):
        """ Method to return a dictionary of relevant info for the process log """
        info = {
            'created': self.created,
            'type': 'create-study',
            'owner': self.owner,
            'access_code_code': self.access_code,
            'name': self.study_name
        }
        return info

    def run(self):
        """
        Thread that handles the creation of a study document
        """
        self.study.update(is_active=True)
        self.study.save()
        Logger.debug('Handling creation of study {} for user {}'.format(self.study_name, self.owner))

        # Get user information from SQL
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
        self.study.update(email=self.email)

        # If the metadata is to be made public overwrite the user_id
        if self.public:
            self.user_id = 1
        self.check_file = fig.DATABASE_DIR / 'last_check.dat'

        # Send the confirmation email
        send_email(self.email, self.owner, message='upload', study=self.study_name,
                   code=self.access_code, testing=self.testing)

        # Update the doc to reflect the successful upload
        self.study.update(is_active=False, exit_code=0)
        self.study.save()
        return 0
