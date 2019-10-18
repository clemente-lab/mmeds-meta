from unittest import TestCase
import mmeds.config as fig

from mmeds.authentication import add_user, remove_user
from mmeds.database import upload_metadata, Database
from pathlib import Path

import mmeds.secrets as sec
import mmeds.documents as docs
import mmeds.util as util
import mongoengine as men


TESTING = True


class DocTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        """ Set up tests """
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=True)

        test_setup = (fig.TEST_METADATA_SHORTEST,
                      fig.TEST_DIR,
                      fig.TEST_USER,
                      'Test_Document',
                      'single_end',
                      fig.TEST_READS,
                      None,
                      fig.TEST_BARCODES,
                      fig.TEST_CODE)
        access_code, email = upload_metadata(test_setup)

        with Database(user='root', testing=TESTING) as db:
            self.test_doc = db.get_docs('study', access_code).first()

        self.connection = men.connect('test', alias='test_documents.py')
        self.test_code = access_code  # 'ThisIsATest'
        self.owner = fig.TEST_USER  # 'test_owner'
        self.email = fig.TEST_EMAIL  # 'test_email'
        """
        self.test_doc = docs.StudyDoc(study_type='test_study',
                                      reads_type='single_end',
                                      study='TestStudy',
                                      access_code=self.test_code,
                                      owner=self.owner,
                                      email=self.email,
                                      path=gettempdir(),
                                      testing=True)
        self.test_doc.save()
        """

    @classmethod
    def tearDownClass(self):
        """ Clean up """
        remove_user(fig.TEST_USER, testing=True)

    def test_creation(self):
        """"""
        self.create_from_study()
        self.create_from_analysis()

    def create_from_study(self):
        """ Test creating a document """
        config = util.load_config(None, fig.TEST_METADATA)
        sd = docs.StudyDoc.objects(access_code=self.test_code).first()
        ad = sd.generate_AnalysisDoc('testDocument', 'qiime2-DADA2', config, fig.TEST_CODE_DEMUX)
        assert Path(sd.path) == Path(ad.path).parent
        assert sd.owner == ad.owner
        assert sd.access_code == ad.study_code

    def create_from_analysis(self):
        ad = docs.AnalysisDoc.objects(access_code=fig.TEST_CODE_DEMUX).first()
        ad2 = ad.create_sub_analysis('Nationality', 'American', 'child_code')
        assert ad2.owner == ad.owner
        print(ad)
        print(ad2)
        assert Path(ad.path) == Path(ad2.path).parent
