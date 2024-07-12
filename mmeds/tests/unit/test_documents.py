from unittest import TestCase
from pathlib import Path
import mongoengine as men

from mmeds.database.database import Database
import mmeds.config as fig
import mmeds.database.documents as docs
import mmeds.util as util


TESTING = True


class DocumentsTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        """ Set up tests """
        with Database(user='root', testing=TESTING) as db:
            self.test_doc = db.get_docs(access_code=fig.TEST_CODE).first()

        self.connection = men.connect('test', alias='test_documents.py')
        self.test_code = fig.TEST_CODE_SHORT
        self.owner = fig.TEST_USER  # 'test_owner'

    def test_creation(self):
        """"""
        self.create_from_study()
        self.create_from_analysis()

    def create_from_study(self):
        """ Test creating a document """
        config = util.load_config(None, fig.TEST_METADATA, 'qiime2')
        sd = docs.MMEDSDoc.objects(access_code=self.test_code).first()
        ad = sd.generate_MMEDSDoc('testDocument', 'qiime2', 'DADA2', config, 'test_documents')
        self.assertEqual(Path(sd.path), Path(ad.path).parent)
        self.assertEqual(sd.owner, ad.owner)
        self.assertEqual(sd.access_code, ad.study_code)

    def create_from_analysis(self):
        ad = docs.MMEDSDoc.objects(access_code='test_documents').first()
        ad2 = ad.generate_sub_analysis_doc(('Subject', 'Nationality'), 'American', 'child_code')
        self.assertEqual(ad2.owner, ad.owner)
        self.assertEqual(Path(ad.path), Path(ad2.path).parent)
