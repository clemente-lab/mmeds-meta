from unittest import TestCase

from mmeds.authentication import add_user, remove_user
from mmeds.tools import Tool

from shutil import rmtree
import mmeds.config as fig


class ToolTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL, testing=True)
        add_user(fig.TEST_USER_0, fig.TEST_PASS, fig.TEST_EMAIL, testing=True)
        self.tool = Tool(fig.TEST_USER,
                         fig.TEST_CODE,
                         'test-1',
                         None, True,
                         10, True)
        self.dirs = []

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)
        remove_user(fig.TEST_USER_0, testing=True)
        for new_dir in self.dirs:
            rmtree(new_dir)

    def test_setup_dir(self):
        new_dir, run_id, files = self.tool.setup_dir(fig.DATABASE_DIR / 'test_dir')
        self.dirs.append(new_dir)

        assert int(run_id) == 0
        assert new_dir == fig.DATABASE_DIR / 'test_dir/analysis0'

        for file_key in ['barcodes', 'reads', 'metadata']:
            assert (file_key in files.keys())

    def test_read_config_file(self):
        pass

    def test_get_job_params(self):
        pass

    def test_move_user_files(self):
        self.tool.move_user_files()
        for f in self.dirs[0].glob('*'):
            print(f)


tt = ToolTests()

tt.setUpClass()
tt.test_setup_dir()
tt.test_move_user_files()
tt.tearDownClass()
