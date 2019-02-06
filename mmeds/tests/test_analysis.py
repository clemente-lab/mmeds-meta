from mmeds import spawn
from mmeds.authentication import add_user, remove_user
from mmeds.database import Database
from mmeds.summary import summarize_qiime
from unittest import TestCase
from pathlib import Path
from time import sleep

import mmeds.config as fig


class AnalysisTests(TestCase):

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, fig.TEST_PASS, fig.TEST_EMAIL, testing=True)
        self.code = None
        self.files = None
        self.path = None

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)

    def handle_data_upload(self):
        """ Test the uploading of data """
        with open(fig.TEST_METADATA, 'rb') as reads, open(fig.TEST_BARCODES, 'rb') as barcodes:
            self.code = spawn.handle_data_upload(Path(fig.TEST_METADATA_SHORT),
                                                 (Path(fig.TEST_METADATA).name, reads),
                                                 (Path(fig.TEST_BARCODES).name, barcodes),
                                                 fig.TEST_USER,
                                                 True)
        # Get the files to check
        with Database(owner=fig.TEST_USER, testing=True) as db:
            self.files, self.path = db.get_mongo_files(access_code=self.code)

        # Check the files exist and their contents match the initial uploads
        self.assertEqual(Path(self.files['metadata']).read_bytes(), Path(fig.TEST_METADATA_SHORT).read_bytes())
        self.assertEqual(Path(self.files['reads']).read_bytes(), Path(fig.TEST_METADATA).read_bytes())
        self.assertEqual(Path(self.files['barcodes']).read_bytes(), Path(fig.TEST_BARCODES).read_bytes())

    def handle_modify_data(self):
        """ Test the modification of a previous upload. """
        with open(fig.TEST_READS, 'rb') as reads:
            spawn.handle_modify_data(self.code,
                                     (Path(fig.TEST_READS).name, reads),
                                     fig.TEST_USER,
                                     'reads',
                                     True)

        # Update the files
        with Database(owner=fig.TEST_USER, testing=True) as db:
            self.files, self.path = db.get_mongo_files(access_code=self.code)

        # Check the files exist and their contents match the initial uploads
        self.assertEqual(Path(self.files['reads']).read_bytes(), Path(fig.TEST_READS).read_bytes())

    def spawn_analysis(self, tool, count):
        p = spawn.spawn_analysis(tool,
                                 fig.TEST_USER,
                                 self.code,
                                 Path(fig.TEST_CONFIG).read_text(),
                                 True)
        while p.is_alive():
            sleep(5)
        self.assertTrue((Path(self.path) / 'analysis{}/summary/analysis.pdf'.format(count)).is_file())

    def summarize(self, count, tool):
        analysis_path = Path(self.path) / 'analysis{}'.format(count)
        summarize_qiime(analysis_path,
                        'module load {}'.format(tool),
                        analysis_path / 'config_file.txt',
                        tool)
        self.assertTrue((Path(self.path) / 'analysis{}/summary/analysis.pdf'.format(count)).is_file())

    def test_spawn_functions(self):
        self.handle_data_upload()
        self.handle_modify_data()
        self.spawn_analysis('qiime1-closed', 0)
        self.summarize(0, 'qiime1')
        self.spawn_analysis('qiime2-dada2', 1)
        self.summarize(1, 'qiime2')
