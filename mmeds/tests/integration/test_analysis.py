from mmeds import spawn
from mmeds.authentication import add_user, remove_user
from mmeds.database import Database
from mmeds.summary import summarize_qiime
from unittest import TestCase
from pathlib import Path
from time import sleep
from shutil import rmtree
import mmeds.config as fig
import mmeds.secrets as sec


class AnalysisTests(TestCase):
    testing = True
    count = 0

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=self.testing)
        self.code = None
        self.files = None
        self.path = None

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=self.testing)

    def handle_data_upload(self, metadata=fig.TEST_METADATA_SHORTEST):
        """ Test the uploading of data """
        with open(fig.TEST_METADATA, 'rb') as reads, open(fig.TEST_BARCODES, 'rb') as barcodes:
            self.code = spawn.handle_data_upload(Path(metadata),
                                                 fig.TEST_USER,
                                                 'single_end',
                                                 self.testing,
                                                 ('for_reads', Path(fig.TEST_METADATA).name, reads),
                                                 ('barcodes', Path(fig.TEST_BARCODES).name, barcodes))
        # Get the files to check
        with Database(owner=fig.TEST_USER, testing=self.testing) as db:
            self.files, self.path = db.get_mongo_files(access_code=self.code)

        # Check the files exist and their contents match the initial uploads
        self.assertEqual(Path(self.files['metadata']).read_bytes(), Path(metadata).read_bytes())
        self.assertEqual(Path(self.files['for_reads']).read_bytes(), Path(fig.TEST_METADATA).read_bytes())
        self.assertEqual(Path(self.files['barcodes']).read_bytes(), Path(fig.TEST_BARCODES).read_bytes())

    def handle_modify_data(self):
        """ Test the modification of a previous upload. """
        with open(fig.TEST_READS, 'rb') as reads:
            spawn.handle_modify_data(self.code,
                                     (Path(fig.TEST_READS).name, reads),
                                     fig.TEST_USER,
                                     'for_reads',
                                     self.testing)

        # Update the files
        with Database(owner=fig.TEST_USER, testing=self.testing) as db:
            self.files, self.path = db.get_mongo_files(access_code=self.code)

        # Check the files exist and their contents match the initial uploads
        self.assertEqual(Path(self.files['for_reads']).read_bytes(), Path(fig.TEST_READS).read_bytes())

    def summarize(self, count, tool):
        summarize_qiime(tool.path, tool)
        self.assertTrue((tool.path / 'summary/analysis.pdf').is_file())

    """
    def test_qiime1(self):
        self.handle_data_upload()
        self.handle_modify_data()
        p = spawn.spawn_analysis('qiime1-closed', fig.TEST_USER, self.code,
                                 Path(fig.TEST_CONFIG).read_text(),
                                 self.testing)
        while p.is_alive():
            sleep(5)
        self.assertTrue((Path(self.path) / 'Qiime1_1_0/summary/analysis.pdf').is_file())
        for child in p.children:
            self.assertEqual(child.exitcode, 0)
        self.assertEqual(p.exitcode, 0)
        self.summarize(0, p)

    def test_qiime2(self):
        self.handle_data_upload()
        self.handle_modify_data()
        p = spawn.spawn_analysis('qiime2-dada2', fig.TEST_USER, self.code,
                                 Path(fig.TEST_CONFIG).read_text(),
                                 self.testing)
        while p.is_alive():
            sleep(5)
        self.assertTrue((Path(self.path) / 'Qiime2_2_0/summary/analysis.pdf').is_file())
        for child in p.children:
            self.assertEqual(child.exitcode, 0)
        self.assertEqual(p.exitcode, 0)
        self.summarize(0, p)
    """

    def test_error_in_data_files(self):
        self.handle_data_upload()
        p = spawn.spawn_analysis('qiime2-dada2', fig.TEST_USER, self.code,
                                 Path(fig.TEST_CONFIG).read_text(),
                                 self.testing)
        code = p.doc.analysis_code
        while p.is_alive():
            sleep(5)
        print(p.doc.path)
        self.assertEqual(p.exitcode, 1)
        self.handle_modify_data()
        tool = spawn.restart_analysis(fig.TEST_USER, code, 0, self.testing)
        print(tool.doc.path)
        tool.start()
        while tool.is_alive():
            sleep(5)
        self.assertEqual(tool.exitcode, 0)
