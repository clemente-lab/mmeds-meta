from unittest import TestCase
from shutil import rmtree
from time import sleep
from multiprocessing import current_process, Queue

from mmeds.authentication import add_user, remove_user
from mmeds.qiime2 import Qiime2
from mmeds.database import upload_metadata
from mmeds.util import load_config

import mmeds.config as fig
import mmeds.secrets as sec
import mmeds.spawn as sp

testing = True


class SpawnTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)

        self.q = Queue()
        self.watcher = sp.Watcher(self.q, current_process(), testing)
        self.watcher.start()
        test_setup = (fig.TEST_METADATA_SHORTEST,
                      fig.TEST_DIR,
                      fig.TEST_USER,
                      'Test_Spawn',
                      'single_end',
                      fig.TEST_READS,
                      None,
                      fig.TEST_BARCODES,
                      fig.TEST_CODE)

        """
        upload_metadata(test_setup)
        self.config = load_config(None, fig.TEST_METADATA_SHORTEST)
        self.tool = Qiime2(owner=fig.TEST_USER,
                           access_code=fig.TEST_CODE,
                           atype='qiime2-dada2',
                           config=self.config,
                           testing=True,
                           analysis=False)
        self.access_code = self.tool.doc.access_code
        self.dirs = [self.tool.doc.path]
        self.tool.start()
        while self.tool.is_alive():
            sleep(5)
        """

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=True)

    def test_a_upload_data(self):
        """ Test uploading data through the queue """
        test_files = {'for_reads': fig.TEST_READS, 'barcodes': fig.TEST_BARCODES}

        # Add multiple uploads from different users
        self.q.put(('upload', 'test_spawn', fig.TEST_SUBJECT, fig.TEST_SPECIMEN,
                    fig.TEST_USER, 'single_end', test_files, False, False))

        self.q.put(('upload', 'test_spawn_0', fig.TEST_SUBJECT_ALT, fig.TEST_SPECIMEN_ALT,
                    fig.TEST_USER_0, 'single_end', test_files, False, False))

        # While the upload process is running wait
        sleep(5)
        running_processes, processes = self.watcher.get_processes()
        print('check running {}'.format(running_processes))
        while running_processes['upload']:
            print('check running {}'.format(running_processes))
            sleep(3)
            running_processes, processes = self.watcher.get_processes()
        sleep(5)
        print('check now')
        # Make sure all processes exited successfully
        for process in processes['upload']:
            print('{} code {}'.format(process.name, process.exitcode))
            self.assertEqual(process.exitcode, 0)

    def test_b_start_analysis(self):
        """ Test starting analysis through the queue """
        return
        self.q.put(('analysis', self.get_user(), access_code, tool, config_text))

    def test_c_restart_analysis(self):
        """ Test restarting an analysis from a analysis doc. """
        return
        tool = sp.restart_analysis(fig.TEST_USER, self.access_code, 1, self.testing, run_analysis=False)
        self.assertTrue(tool)
        self.assertEqual(tool.doc, self.tool.doc)
        tool.start()
        while tool.is_alive():
            sleep(5)
        self.assertEqual(tool.exitcode, 0)
        self.assertTrue(tool.get_file('jobfile', True).is_file())

    def test_d_start_sub_analysis_cold(self):
        """ Test that a sub-analysis can be successfully started from a previously run analysis. """
        return
        tool = sp.spawn_sub_analysis(fig.TEST_USER, self.access_code,
                                     ('BodySite', 'SpecimenBodySite'),
                                     'tongue', self.testing)
        self.assertTrue(tool)
