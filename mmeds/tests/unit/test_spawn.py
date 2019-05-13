from unittest import TestCase
from shutil import rmtree

from mmeds.authentication import add_user, remove_user
from mmeds.tool import Tool
from mmeds.database import MetaDataUploader, Database
from mmeds.util import load_config

import mongoengine as men

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
        self.tool = Tool(fig.TEST_USER,
                         fig.TEST_CODE,
                         'qiime2-dada2',
                         self.config, True,
                         8, True)
        self.analysis_code = self.tool.doc.analysis_code
        self.dirs = [self.tool.doc.path]

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)
        for new_dir in self.dirs:
            rmtree(new_dir)

    def test_start_sub_analysis_cold(self):
        """ Test that a sub-analysis can be successfully started from a previously run analysis. """
        # TODO

    def test_restart_analysis(self):
        """ Test restarting an analysis from a analysis doc. """
        tool = sp.restart_analysis(fig.TEST_USER, self.analysis_code, self.testing)
        assert tool

    def test_start_analysis(self):
        """ Test starting an analysis from a study doc. """
        # TODO
