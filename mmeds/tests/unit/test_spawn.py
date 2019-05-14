from unittest import TestCase
from shutil import rmtree
from time import sleep

from mmeds.authentication import add_user, remove_user
from mmeds.tool import Tool
from mmeds.qiime2 import Qiime2
from mmeds.database import MetaDataUploader
from mmeds.util import load_config

import mmeds.config as fig
import mmeds.secrets as sec
import mmeds.spawn as sp


def upload_metadata(args):
    metadata, path, owner, access_code = args
    with MetaDataUploader(metadata=metadata,
                          path=path,
                          study_type='qiime',
                          reads_type='single_end',
                          owner=fig.TEST_USER,
                          testing=True) as up:
        access_code, study_name, email = up.import_metadata(for_reads=fig.TEST_READS,
                                                            barcodes=fig.TEST_BARCODES,
                                                            access_code=access_code)


class SpawnTests(TestCase):
    """ Tests of top-level functions """
    testing = True

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=True)
        test_setup = (fig.TEST_METADATA_SHORTEST,
                      fig.TEST_DIR,
                      fig.TEST_USER,
                      fig.TEST_CODE)
        upload_metadata(test_setup)
        self.config = load_config(None, fig.TEST_METADATA_SHORTEST)
        self.tool = Qiime2(owner=fig.TEST_USER,
                           access_code=fig.TEST_CODE,
                           atype='qiime2-dada2',
                           config=self.config,
                           testing=True,
                           analysis=False,
                           restart=False)
        self.analysis_code = self.tool.doc.analysis_code
        self.dirs = [self.tool.doc.path]
        self.tool.start()
        while self.tool.is_alive():
            sleep(5)

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)
        #for new_dir in self.dirs:
        #    rmtree(new_dir)

    def test_c_start_sub_analysis_cold(self):
        """ Test that a sub-analysis can be successfully started from a previously run analysis. """
        print(self.tool.doc)
        child = self.tool.create_child('SpecimenBodySite', 'tongue')
        self.assertTrue(child)

    def test_b_restart_analysis(self):
        """ Test restarting an analysis from a analysis doc. """
        tool = sp.restart_analysis(fig.TEST_USER, self.analysis_code, self.testing)
        self.assertTrue(tool)
        self.assertEqual(tool.doc, self.tool.doc)
        print(tool.path)
        tool.start()
        while tool.is_alive():
            sleep(5)
        self.assertEqual(tool.exitcode, 0)
        self.assertTrue((tool.path / 'jobfile.lsf').is_file())
