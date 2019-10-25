from unittest import TestCase
from shutil import rmtree
from time import sleep

from mmeds.authentication import add_user, remove_user
from mmeds.qiime2 import Qiime2
from mmeds.database import upload_metadata
from mmeds.util import load_config

from yaml import safe_load

import mmeds.config as fig
import mmeds.secrets as sec
import mmeds.spawn as sp
import multiprocessing as mp

testing = True


class SpawnTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)
        add_user(fig.TEST_USER_0, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)

        self.q = mp.Queue()
        self.manager = mp.Manager()
        self.current_processes = self.manager.list()
        pipe_ends = mp.Pipe()
        self.pipe = pipe_ends[0]
        self.watcher = sp.Watcher(self.q, pipe_ends[1], mp.current_process(), testing)
        self.watcher.start()
        self.infos = []

    @classmethod
    def tearDownClass(self):
        self.watcher.terminate()
        remove_user(fig.TEST_USER, testing=True)
        remove_user(fig.TEST_USER_0, testing=True)

    def test_a_upload_data(self):
        """ Test uploading data through the queue """
        test_files = {'for_reads': fig.TEST_READS, 'barcodes': fig.TEST_BARCODES}

        # Add multiple uploads from different users
        self.q.put(('upload', 'test_spawn', fig.TEST_SUBJECT, fig.TEST_SPECIMEN,
                    fig.TEST_USER, 'single_end', test_files, False, False))

        self.q.put(('upload', 'test_spawn_0', fig.TEST_SUBJECT_ALT, fig.TEST_SPECIMEN_ALT,
                    fig.TEST_USER_0, 'single_end', test_files, False, False))

        # Recieve the process info dicts from Watcher
        # Sent one at time b/c only one upload can happen at a time
        for i in [0, 1]:
            info = self.pipe.recv()
            # Check they match the contents of current_processes
            with open(fig.CURRENT_PROCESSES, 'r') as f:
                procs = safe_load(f)
            self.infos += procs
            self.assertEqual([info], procs)
            # Check the process exited with code 0
            self.assertEqual(self.pipe.recv(), 0)

        # Wait for watcher to update current_processes
        sleep(5)

        # Check they've been removed from processes currently running
        with open(fig.CURRENT_PROCESSES, 'r') as f:
            procs = safe_load(f)
        self.assertEqual([], procs)

    def test_b_start_analysis(self):
        """ Test starting analysis through the queue """
        tool = 'test-20'
        for proc in self.infos:
            self.q.put(('analysis', proc['owner'], proc['study_code'], tool, None))

        # Check the analyses are started and running simultainiously
        info = self.pipe.recv()
        info_0 = self.pipe.recv()
        sleep(5)
        # Check they match the contents of current_processes
        with open(fig.CURRENT_PROCESSES, 'r') as f:
            procs = safe_load(f)
        self.assertEqual([info, info_0], procs)

        # Check the process exited with code 0
        self.assertEqual(self.pipe.recv(), 0)
        self.assertEqual(self.pipe.recv(), 0)

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
