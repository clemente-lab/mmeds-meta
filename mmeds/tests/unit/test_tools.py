from unittest import TestCase
from shutil import rmtree
from pathlib import Path
from time import sleep

from mmeds.authentication import add_user, remove_user
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.sparcc import SparCC
from mmeds.database import upload_metadata, upload_otu
from mmeds.util import load_config
import mmeds.config as fig
import mmeds.secrets as sec


class QiimeTests(TestCase):
    """ Tests of top-level functions """
    testing = True

    @classmethod
    def setUpClass(self):
        self.TEST_CODE = 'qiimeTest'
        self.TEST_CODE_PAIRED = 'qiimeTestPaired'
        self.TEST_CODE_DEMUX = 'qiimeTestDemuxed'
        self.TEST_CODE_OTU = 'qiimeTestOTU'

        test_otu = (fig.TEST_SUBJECT,
                    fig.TEST_SPECIMEN,
                    fig.TEST_DIR,
                    fig.TEST_USER,
                    'Test_SparCC',
                    fig.TEST_OTU,
                    self.TEST_CODE_OTU)
        assert 0 == upload_otu(test_otu)
        # Ensure the uploads completed correctly
        self.config = load_config(None, fig.TEST_METADATA_SHORT)

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=self.testing)

    def run_qiime(self, code, atype, data_type, Qiime):
        qiime = Qiime(fig.TEST_USER, code, atype, self.config, testing=self.testing, analysis=False)
        qiime.start()
        while qiime.is_alive():
            sleep(2)
        self.assertEqual(qiime.doc.data_type, data_type)
        rmtree(qiime.path)

    def test_sparcc_setup_analysis(self):
        self.run_qiime(self.TEST_CODE_OTU, 'sparcc', 'otu_table', SparCC)

    def test_qiime1_setup_analysis(self):
        for atype in ['qiime1-open', 'qiime1-closed']:
            for code in [('single_end', fig.TEST_CODE),
                         ('paired_end', fig.TEST_CODE_PAIRED),
                         ('single_end_demuxed', fig.TEST_CODE_DEMUX)]:
                self.run_qiime(code[1], atype, code[0], Qiime1)

    def test_qiime2_setup_analysis(self):
        for atype in ['qiime2-dada2', 'qiime2-deblur']:
            for code in [('single_end', fig.TEST_CODE),
                         ('paired_end', fig.TEST_CODE_PAIRED),
                         ('single_end_demuxed', fig.TEST_CODE_DEMUX)]:
                self.run_qiime(code[1], atype, code[0], Qiime2)

    def test_qiime2_child_setup_analysis(self):
        config = load_config(Path(fig.TEST_CONFIG).read_text(), fig.TEST_METADATA)
        q2 = Qiime2(fig.TEST_USER, fig.TEST_CODE, 'qiime2-dada2', config, True, analysis=False)
        q2.setup_analysis()
        q2.create_children()
        for child in q2.children:
            self.assertEqual(child.doc.data_type, 'single_end')

        rmtree(q2.path)
