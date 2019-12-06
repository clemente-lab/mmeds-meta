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

        test_setup = (fig.TEST_SUBJECT,
                      fig.TEST_SPECIMEN,
                      fig.TEST_DIR,
                      fig.TEST_USER,
                      'Test_Document',
                      'single_end',
                      fig.TEST_READS,
                      None,
                      fig.TEST_BARCODES,
                      fig.TEST_CODE)
        upload_metadata(test_setup)

        with Database(user='root', testing=TESTING) as db:
            self.test_doc = db.get_docs('study', fig.TEST_CODE).first()

        self.connection = men.connect('test', alias='test_documents.py')
        self.test_code = fig.TEST_CODE
        self.owner = fig.TEST_USER  # 'test_owner'

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
        sd = docs.MMEDSDoc.objects(access_code=self.test_code).first()
        ad = sd.generate_MMEDSDoc('testDocument', 'qiime2-DADA2', config, fig.TEST_CODE_DEMUX, 'some_directory')
        self.assertEqual(Path(sd.path), Path(ad.path).parent)
        self.assertEqual(sd.owner, ad.owner)
        self.assertEqual(sd.access_code, ad.study_code)

    def create_from_analysis(self):
        ad = docs.MMEDSDoc.objects(access_code=fig.TEST_CODE_DEMUX).first()
        ad2 = ad.create_sub_analysis('Nationality', 'American', 'child_code')
        self.assertEqual(ad2.owner, ad.owner)
        self.assertEqual(Path(ad.path), Path(ad2.path).parent)
