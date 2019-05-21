from unittest import TestCase
from shutil import rmtree
from pathlib import Path
from time import sleep

from mmeds.authentication import add_user, remove_user
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.database import MetaDataUploader
from mmeds.util import load_config
import mmeds.config as fig
import mmeds.secrets as sec


def upload_metadata(args):
    metadata, path, owner, reads_type, for_reads, rev_reads, barcodes, access_code = args
    with MetaDataUploader(metadata=metadata,
                          path=path,
                          study_type='qiime',
                          reads_type=reads_type,
                          owner=fig.TEST_USER,
                          testing=True) as up:
        access_code, study_name, email = up.import_metadata(for_reads=for_reads,
                                                            rev_reads=rev_reads,
                                                            barcodes=barcodes,
                                                            access_code=access_code)


class QiimeTests(TestCase):
    """ Tests of top-level functions """
    testing = True

    @classmethod
    def setUpClass(self):
        self.TEST_CODE = 'qiimeTest'
        self.TEST_CODE_PAIRED = 'qiimeTestPaired'
        self.TEST_CODE_DEMUX = 'qiimeTestDemuxed'
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=self.testing)
        test_setups = [
            (fig.TEST_METADATA_SHORT,
             fig.TEST_DIR,
             fig.TEST_USER,
             'single_end',
             fig.TEST_READS,
             None,
             fig.TEST_BARCODES,
             self.TEST_CODE),
            (fig.TEST_METADATA_SHORT,
             fig.TEST_DIR,
             fig.TEST_USER,
             'paired_end',
             fig.TEST_READS,
             fig.TEST_REV_READS,
             fig.TEST_BARCODES,
             self.TEST_CODE_PAIRED),
            (fig.TEST_METADATA_SHORT,
             fig.TEST_DIR,
             fig.TEST_USER,
             'single_end',
             fig.TEST_DEMUXED,
             None,
             fig.TEST_BARCODES,
             self.TEST_CODE_DEMUX)
        ]
        for test_setup in test_setups:
            upload_metadata(test_setup)
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

    def test_qiime1_setup_analysis(self):
        for atype in ['qiime1-open', 'qiime1-closed']:
            for code in [('single_end', self.TEST_CODE),
                         ('paired_end', self.TEST_CODE_PAIRED),
                         ('single_end_demuxed', self.TEST_CODE_DEMUX)]:
                self.run_qiime(code[1], atype, code[0], Qiime1)

    def test_qiime2_setup_analysis(self):
        for atype in ['qiime2-dada2', 'qiime2-deblur']:
            for code in [('single_end', self.TEST_CODE),
                         ('paired_end', self.TEST_CODE_PAIRED),
                         ('single_end_demuxed', self.TEST_CODE_DEMUX)]:
                self.run_qiime(code[1], atype, code[0], Qiime2)

    def test_qiime2_child_setup_analysis(self):
        config = load_config(Path(fig.TEST_CONFIG).read_text(), fig.TEST_METADATA)
        q2 = Qiime2(fig.TEST_USER, self.TEST_CODE, 'qiime2-dada2', config, True, analysis=False)
        q2.setup_analysis()
        q2.create_children()
        for child in q2.children:
            self.assertEqual(child.doc.data_type, 'single_end')

        rmtree(q2.path)
