from unittest import TestCase
import mmeds.config as fig

from mmeds.authentication import add_user, remove_user
from mmeds.database import MetaDataUploader
from pathlib import Path
from tempfile import gettempdir

import mmeds.secrets as sec
import mmeds.documents as docs
import mmeds.util as util
import mongoengine as men


def upload_metadata(args):
    metadata, path, owner, access_code = args
    with MetaDataUploader(metadata=metadata,
                          path=path,
                          study_name='Test_Documents',
                          study_type='qiime',
                          reads_type='single_end',
                          owner=fig.TEST_USER,
                          temporary=False,
                          testing=True) as up:
        access_code, study_name, email = up.import_metadata(for_reads=fig.TEST_READS,
                                                            barcodes=fig.TEST_BARCODES,
                                                            access_code=access_code)


class DocTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        """ Set up tests """
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=True)
        self.connection = men.connect('test', alias='test_documents.py')
        self.test_code = 'ThisIsATest'
        self.owner = fig.TEST_USER  # 'test_owner'
        self.email = fig.TEST_EMAIL  # 'test_email'
        self.test_doc = docs.StudyDoc(study_type='test_study',
                                      reads_type='single_end',
                                      study='TestStudy',
                                      access_code=self.test_code,
                                      owner=self.owner,
                                      email=self.email,
                                      path=gettempdir(),
                                      testing=True)
        self.test_doc.save()

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
        assert sd.owner == ad.owner

    def create_from_analysis(self):
        ad = docs.AnalysisDoc(access_code=fig.TEST_CODE_DEMUX).first()
        ad2 = ad.create_copy()
        print(ad2)
