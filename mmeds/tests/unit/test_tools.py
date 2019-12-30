from unittest import TestCase
from shutil import rmtree
from pathlib import Path
from time import sleep

from mmeds.authentication import add_user, remove_user
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.sparcc import SparCC
from mmeds.database import upload_metadata, upload_otu
from mmeds.util import load_config, debug_log
import mmeds.config as fig
import mmeds.secrets as sec


class ToolTests(TestCase):
    """ Tests of top-level functions """
    testing = True

    @classmethod
    def setUpClass(self):
        self.TEST_CODE = 'qiimeTest' + fig.get_salt(10)
        self.TEST_CODE_PAIRED = 'qiimeTestPaired' + fig.get_salt(10)
        self.TEST_CODE_DEMUX = 'qiimeTestDemuxed' + fig.get_salt(10)
        self.TEST_CODE_OTU = 'qiimeTestOTU' + fig.get_salt(10)
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=self.testing)
        test_setups = [
            (fig.TEST_SUBJECT,
             fig.TEST_SPECIMEN,
             fig.TEST_DIR,
             fig.TEST_USER,
             'Test_Qiime_0',
             'single_end',
             'single_barcodes',
             fig.TEST_READS,
             None,
             fig.TEST_BARCODES,
             self.TEST_CODE),
            (fig.TEST_SUBJECT,
             fig.TEST_SPECIMEN,
             fig.TEST_DIR,
             fig.TEST_USER,
             'Test_Qiime_1',
             'paired_end',
             'single_barcodes',
             fig.TEST_READS,
             fig.TEST_REV_READS,
             fig.TEST_BARCODES,
             self.TEST_CODE_PAIRED),
            (fig.TEST_SUBJECT,
             fig.TEST_SPECIMEN,
             fig.TEST_DIR,
             fig.TEST_USER,
             'Test_Qiime_2',
             'single_end_demuxed',
             'single_barcodes',
             fig.TEST_DEMUXED,
             None,
             fig.TEST_BARCODES,
             self.TEST_CODE_DEMUX)
        ]
        for test_setup in test_setups:
            assert 0 == upload_metadata(test_setup)

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

    def run_qiime(self, code, atype, reads_type, Qiime):
        print('atype: {}, data_type: {}'.format(atype, reads_type))

        qiime = Qiime(fig.TEST_USER, code, atype, self.config, testing=self.testing, analysis=False)
        qiime.start()
        while qiime.is_alive():
            sleep(2)
        debug_log('File Keys for {}'.format(qiime.name))
        debug_log(qiime.doc.files.keys())
        self.assertEqual(qiime.doc.reads_type, reads_type)
        rmtree(qiime.path)

    def test_sparcc_setup_analysis(self):
        self.run_qiime(self.TEST_CODE_OTU, 'sparcc-default', 'otu_table', SparCC)

    def test_qiime1_setup_analysis(self):
        return
        for atype in ['qiime1-open', 'qiime1-closed']:
            for code in [('single_end', self.TEST_CODE),
                         ('paired_end', self.TEST_CODE_PAIRED),
                         ('single_end_demuxed', self.TEST_CODE_DEMUX)]:
                self.run_qiime(code[1], atype, code[0], Qiime1)

    def test_qiime2_setup_analysis(self):
        return
        for atype in ['qiime2-dada2', 'qiime2-deblur']:
            for code in [('single_end', self.TEST_CODE),
                         ('paired_end', self.TEST_CODE_PAIRED),
                         ('single_end_demuxed', self.TEST_CODE_DEMUX)]:
                self.run_qiime(code[1], atype, code[0], Qiime2)

    def test_qiime2_child_setup_analysis(self):
        return
        config = load_config(Path(fig.TEST_CONFIG).read_text(), fig.TEST_METADATA)
        q2 = Qiime2(fig.TEST_USER, self.TEST_CODE, 'qiime2-dada2', config, True, analysis=False)
        q2.setup_analysis()
        q2.create_children()
        for child in q2.children:
            self.assertEqual(child.doc.data_type, 'single_end')

        rmtree(q2.path)

    def test_sparcc_sub_analysis(self):
        return
        config = load_config(Path(fig.TEST_CONFIG).read_text(), fig.TEST_METADATA)
        q2 = Qiime2(fig.TEST_USER, self.TEST_CODE, 'qiime2-dada2', config, True, analysis=False)
        q2.setup_analysis()

        print(q2.doc.files.keys())
        q2.create_analysis(SparCC)

        rmtree(q2.path)
