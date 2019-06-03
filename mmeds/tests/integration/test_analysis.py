from mmeds import spawn
from mmeds.authentication import add_user, remove_user
from mmeds.database import Database
from mmeds.summary import summarize_qiime
from mmeds.util import log
from unittest import TestCase
from pathlib import Path
from time import sleep
from datetime import datetime
import mmeds.config as fig
import mmeds.secrets as sec


class AnalysisTests(TestCase):
    testing = False
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
        log('update datagbase files upload')
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

        log('update datagbase files modify')
        # Update the files
        with Database(owner=fig.TEST_USER, testing=self.testing) as db:
            self.files, self.path = db.get_mongo_files(access_code=self.code)

        # Check the files exist and their contents match the initial uploads
        self.assertEqual(Path(self.files['for_reads']).read_bytes(), Path(fig.TEST_READS).read_bytes())

    def summarize(self, count, tool):
        summarize_qiime(tool.path, tool)
        self.assertTrue((tool.path / 'summary/analysis.pdf').is_file())

    def test_qiime1(self):
        log("in test_qiime1")
        self.handle_data_upload()
        log('after data upload')
        self.handle_modify_data()
        log('after data modification')
        p = spawn.spawn_analysis('qiime1-closed', fig.TEST_USER, self.code,
                                 Path(fig.TEST_CONFIG).read_text(),
                                 self.testing)
        log('after spawned analysis')
        while p.is_alive():
            sleep(5)
        log('analysis finished')
        self.assertTrue((Path(self.path) / 'Qiime1_0/summary/analysis.pdf').is_file())
        for child in p.children:
            self.assertEqual(child.exitcode, 0)
        self.assertEqual(p.exitcode, 0)
        self.summarize(0, p)

    def test_qiime2_with_restarts(self):
        self.handle_data_upload()
        p = spawn.spawn_analysis('qiime2-dada2', fig.TEST_USER, self.code,
                                 Path(fig.TEST_CONFIG).read_text(),
                                 self.testing)
        code = p.doc.analysis_code
        while p.is_alive():
            sleep(5)
        self.assertEqual(p.exitcode, 1)

        # Change the metadata file to a proper one
        self.handle_modify_data()
        # Test restarting from the beginning of analysis
        tool = spawn.restart_analysis(fig.TEST_USER, code, 0, self.testing, kill_stage=1)
        tool.start()
        sleep(10)
        # Test restarting from each checkpoint
        for i in range(1, 5):
            while tool.is_alive():
                print('{}: Waiting on stage {}'.format(datetime.now(), i))
                sleep(10)
            # Check it terminated and has the correct restart point
            self.assertNotEqual(tool.exitcode, 0)
            # Have to get a fresh copy of the document from the DB
            # Because the tool object won't have been copied
            sleep(5)
            tool.doc.reload()
            self.assertEqual(tool.doc.restart_stage, i)
            # Restart
            tool = spawn.restart_analysis(fig.TEST_USER, code, tool.doc.restart_stage, self.testing, kill_stage=i + 1)
            tool.start()
        while tool.is_alive():
            print('{}: Waiting on stage {}'.format(datetime.now(), i))
            sleep(10)

        self.assertEqual(tool.exitcode, 0)
        self.assertTrue((Path(self.path) / 'Qiime2_0/summary/analysis.pdf').is_file())
