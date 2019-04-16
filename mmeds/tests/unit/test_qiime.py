from unittest import TestCase
from shutil import rmtree

from mmeds.authentication import add_user, remove_user
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.database import Database
from mmeds.util import load_config
import mmeds.config as fig
import mmeds.secrets as sec


class QiimeTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=True)
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA_SHORT,
                                                              'qiime',
                                                              'single_end',
                                                              for_reads=fig.TEST_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE)
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA_SHORT,
                                                              'qiime',
                                                              'paired_end',
                                                              for_reads=fig.TEST_READS,
                                                              rev_reads=fig.TEST_REV_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE_PAIRED)
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA_SHORT,
                                                              'qiime',
                                                              'single_end',
                                                              for_reads=fig.TEST_DEMUXED,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE_DEMUX)
        self.config = load_config(None, fig.TEST_METADATA_SHORT)

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)

    def run_qiime(self, code, atype, data_type, Qiime):
        qiime = Qiime(fig.TEST_USER, code, atype, self.config, True)
        qiime.setup_analysis()
        self.assertEqual(qiime.data_type, data_type)
        rmtree(qiime.path)

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
