from unittest import TestCase

from mmeds.authentication import add_user, remove_user
from mmeds.tool import Tool
from mmeds.database import Database

from shutil import rmtree
from subprocess import run
import mmeds.config as fig


class ToolTests(TestCase):
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
        self.tool = Tool(fig.TEST_USER,
                         fig.TEST_CODE,
                         'test-1',
                         None, True,
                         8, True)
        self.dirs = [self.tool.path]

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)
        for new_dir in self.dirs:
            rmtree(new_dir)

    def test_setup_dir(self):
        new_dir, run_id, files, demuxed = self.tool.setup_dir(fig.TEST_DIR)
        self.dirs.append(new_dir)

        assert str(fig.TEST_DIR / 'analysis') in str(new_dir)
        assert not demuxed
        assert 'metadata' in files.keys()
        assert files['metadata'].is_symlink()

    def test_add_path(self):
        """ Test that adding files to the tool object works properly """
        assert 'testfile' not in self.tool.files.keys()
        self.tool.add_path('testfile', '.txt')
        assert 'testfile' in self.tool.files.keys()
        assert not self.tool.files['testfile'].is_file()

    def test_read_config_file(self):
        """ Assert that config files are loaded correctly """
        config0 = self.tool.read_config_file(None)
        with open(fig.STORAGE_DIR / 'config_file.txt') as f:
            contents = f.read()
        configd0 = self.tool.config
        config1 = self.tool.read_config_file(contents)
        configd1 = self.tool.config
        assert config0 == config1
        assert configd0 == configd1

    def test_get_job_params(self):
        params = self.tool.get_job_params()
        assert '{}-{}'.format(fig.TEST_USER, 1) in params['jobname']
        assert params['nodes'] == 3

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
