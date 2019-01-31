from unittest import TestCase
from shutil import rmtree

from mmeds.authentication import add_user, remove_user
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.database import Database
import mmeds.config as fig


class QiimeTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL, testing=True)
        with Database(fig.TEST_DIR, user='root', owner=fig.TEST_USER, testing=True) as db:
            access_code, study_name, email = db.read_in_sheet(fig.TEST_METADATA,
                                                              'qiime',
                                                              reads=fig.TEST_READS,
                                                              barcodes=fig.TEST_BARCODES,
                                                              access_code=fig.TEST_CODE)

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)

    def test_qiime1_setup_analysis(self):
        qiime_open = Qiime1(fig.TEST_USER,
                            fig.TEST_CODE,
                            'qiime1-open',
                            None, True)
        qiime_open.setup_analysis()
        rmtree(qiime_open.path)

        qiime_closed = Qiime1(fig.TEST_USER,
                              fig.TEST_CODE,
                              'qiime1-closed',
                              None, True)
        qiime_closed.setup_analysis()
        rmtree(qiime_closed.path)

    def test_qiime2_setup_analysis(self):
        qiime_open = Qiime2(fig.TEST_USER,
                            fig.TEST_CODE,
                            'qiime2-dada2',
                            None, True)
        qiime_open.setup_analysis()
        rmtree(qiime_open.path)

        qiime_closed = Qiime2(fig.TEST_USER,
                              fig.TEST_CODE,
                              'qiime2-deblur',
                              None, True)
        qiime_closed.setup_analysis()
        rmtree(qiime_closed.path)
