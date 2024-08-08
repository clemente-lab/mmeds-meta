from unittest import TestCase, skip
from shutil import rmtree
from multiprocessing import Queue

from mmeds.util import load_config
from mmeds.tools.analysis import Analysis
from mmeds.logging import Logger
import mmeds.config as fig
import mmeds.error as err


class ToolTests(TestCase):
    """ Tests of top-level functions """
    testing = True

    @classmethod
    def setUpClass(self):
        self.q = Queue()
        self.config = load_config('', fig.TEST_METADATA_SHORTEST, 'standard_pipeline')
        self.analysis = Analysis(self.q, fig.TEST_USER, 'some new code', fig.TEST_CODE_SHORT, 'standard_pipeline',
                         'default', 'test', self.config, True, {}, True)
        self.analysis.initial_setup()
        self.dirs = self.analysis.doc.path

    def test_a_add_paths(self):
        """ Test that adding files to the tool object works properly """
        Logger.info(str(self.analysis))
        assert 'testfile' not in self.analysis.doc.files.keys()
        self.analysis.add_path('testfile', '.txt')
        assert 'testfile' in self.analysis.doc.files.keys()

    def test_b_get_job_params(self):
        params = self.analysis.get_job_params()
        assert params['nodes'] == 2

    def test_c_get_files(self):
        """ Test the method for finishing analysis and writing file locations. """
        assert True

    def test_missing_file(self):
        """ Test that an appropriate error will be raised if a file doesn't exist on disk """
        # TODO
        files = self.analysis.doc.files
        # Add a non-existent file
        files['fakefile'] = '/fake/dir/'
        self.analysis.update_doc(files=files)
        with self.assertRaises(err.MissingFileError):
            self.analysis.get_file('fakefile', check=True)
        del files['fakefile']
        self.analysis.update_doc(files=files)

    def test_update_doc(self):
        self.assertEqual(self.analysis.doc.study_name, 'Test_Single_Short')
        self.analysis.update_doc(study_name='Test_Update')
        self.assertEqual(self.analysis.doc.study_name, 'Test_Update')
