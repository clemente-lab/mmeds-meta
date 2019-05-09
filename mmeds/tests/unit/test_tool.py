from unittest import TestCase
from shutil import rmtree

from mmeds.authentication import add_user, remove_user
from mmeds.tool import Tool
from mmeds.database import MetaDataUploader, Database
from mmeds.util import load_config

import mongoengine as men

import mmeds.config as fig
import mmeds.secrets as sec


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


class ToolTests(TestCase):
    """ Tests of top-level functions """
    testing = True

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=True)
        test_setup = (fig.TEST_METADATA,
                      fig.TEST_DIR,
                      fig.TEST_USER,
                      fig.TEST_CODE)
        upload_metadata(test_setup)
        self.config = load_config(None, fig.TEST_METADATA)
        self.tool = Tool(fig.TEST_USER,
                         fig.TEST_CODE,
                         'test-1',
                         self.config, True,
                         8, True)
        self.dirs = [self.tool.doc.path]

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)
        for new_dir in self.dirs:
            rmtree(new_dir)

    def test_add_path(self):
        """ Test that adding files to the tool object works properly """
        assert 'testfile' not in self.tool.doc.files.keys()
        self.tool.add_path('testfile', '.txt')
        assert 'testfile' in self.tool.doc.files.keys()

    def test_get_job_params(self):
        params = self.tool.get_job_params()
        assert params['nodes'] == 2

    def test_move_user_files(self):
        """ Test the method for finishing analysis and writing file locations. """
        self.tool.add_path('test1', '.qzv')
        self.tool.add_path('test2', '.qzv')

        (self.tool.path / 'test1.qzv').touch()
        (self.tool.path / 'test2.qzv').touch()

        self.tool.move_user_files()

        assert (self.tool.path / 'visualizations_dir').is_dir()
        assert ((self.tool.path / 'visualizations_dir') / 'test1.qzv').is_file()
        assert ((self.tool.path / 'visualizations_dir') / 'test2.qzv').is_file()

    def test_missing_file(self):
        """ Test that an appropriate error will be raised if a file doesn't exist on disk """
        # TODO

    def test_start_sub_analysis_cold(self):
        """ Test that a sub-analysis can be successfully started from a previously run analysis. """
        # TODO

    def test_restart_analysis(self):
        """ Test restarting an analysis from a analysis doc. """
        # TODO

    def test_start_analysis(self):
        """ Test starting an analysis from a study doc. """
        # TODO
