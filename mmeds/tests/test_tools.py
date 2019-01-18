from unittest import TestCase

from mmeds.authentication import add_user, remove_user
from mmeds.tools import Tool
from mmeds.database import Database

from shutil import rmtree
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
                         10, True)
        self.dirs = [self.tool.path]

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)
        for new_dir in self.dirs:
            rmtree(new_dir)

    def test_setup_dir(self):
        new_dir, run_id, files = self.tool.setup_dir(fig.TEST_DIR)
        self.dirs.append(new_dir)

        assert int(run_id) == 1
        assert new_dir == fig.TEST_DIR / 'analysis1'

        for file_key in ['barcodes', 'reads', 'metadata']:
            assert (file_key in files.keys())
            assert files[file_key].is_symlink()

    def test_add_path(self):
        """ Test that adding files to the tool object works properly """
        assert 'testfile' not in self.tool.files.keys()
        self.tool.add_path('testfile', '.txt')

        assert 'testfile' in self.tool.files.keys()
        assert (fig.TEST_DIR / 'analysis0') / 'testfile.txt' == self.tool.files['testfile']

    def test_read_config_file(self):
        pass

    def test_get_job_params(self):
        pass

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


tt = ToolTests()

tt.setUpClass()
tt.test_setup_dir()
tt.test_add_path()
tt.test_move_user_files()
tt.tearDownClass()
