from unittest import TestCase
from shutil import rmtree

from mmeds.authentication import add_user, remove_user
from mmeds.tool import Tool
from mmeds.database import upload_metadata
from mmeds.util import load_config

import mmeds.config as fig
import mmeds.secrets as sec
import mmeds.error as err


class ToolTests(TestCase):
    """ Tests of top-level functions """
    testing = True

    @classmethod
    def setUpClass(self):
        self.config = load_config(None, fig.TEST_METADATA_SHORTEST)
        self.tool = Tool(fig.TEST_USER, fig.TEST_CODE, 'test-1', self.config, True, 2, True)
        self.dirs = [self.tool.doc.path]

    @classmethod
    def tearDownClass(self):
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
        files = self.tool.doc.files
        # Add a non-existent file
        files['fakefile'] = '/fake/dir/'
        self.tool.update_doc(files=files)
        with self.assertRaises(err.MissingFileError):
            self.tool.get_file('fakefile', check=True)
        del files['fakefile']
        self.tool.update_doc(files=files)

    def test_update_doc(self):
        self.assertEqual(self.tool.doc.study_name, 'Test_Single')
        self.tool.update_doc(study_name='Test_Update')
        self.assertEqual(self.tool.doc.study_name, 'Test_Update')
