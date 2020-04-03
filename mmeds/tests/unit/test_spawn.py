from unittest import TestCase
from time import sleep

from yaml import safe_load

from mmeds.log import MMEDSLog
import mmeds.config as fig
import mmeds.spawn as sp
import multiprocessing as mp
import sys

testing = True

logger = MMEDSLog('debug').logger


class SpawnTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        self.q = mp.Queue()
        self.manager = mp.Manager()
        self.current_processes = self.manager.list()
        pipe_ends = mp.Pipe()
        self.pipe = pipe_ends[0]
        self.watcher = sp.Watcher(self.q, pipe_ends[1], mp.current_process(), testing)
        self.watcher.start()
        self.infos = []
        self.analyses = []

    @classmethod
    def tearDownClass(self):
        self.watcher.terminate()

    def test_a_upload_data(self):
        """ Test uploading data through the queue """
        test_files = {'for_reads': fig.TEST_READS, 'barcodes': fig.TEST_BARCODES}

        # Add multiple uploads from different users
        self.q.put(('upload', 'test_spawn', fig.TEST_SUBJECT_SHORT, 'human', fig.TEST_SPECIMEN_SHORT,
                    fig.TEST_USER, 'single_end', 'single_barcodes', test_files, False, False))

        self.q.put(('upload', 'test_spawn_0', fig.TEST_SUBJECT_SHORT, 'human', fig.TEST_SPECIMEN_SHORT,
                    fig.TEST_USER_0, 'single_end', 'single_barcodes', test_files, False, False))

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
        sys.stderr.write('Upload data finished')

    def test_b_start_analysis(self):
        """ Test starting analysis through the queue """
        for proc in self.infos:
            self.q.put(('analysis', proc['owner'], proc['access_code'], 'test', '20', None, True, -1))

        sys.stderr.write('Waiting on analysis')
        # Check the analyses are started and running simultainiously
        info = self.pipe.recv()
        info_0 = self.pipe.recv()
        self.analyses += [info, info_0]
        sleep(2)

        # Check they match the contents of current_processes
        with open(fig.CURRENT_PROCESSES, 'r') as f:
            procs = safe_load(f)

        self.assertEqual(info, procs[0])
        self.assertEqual(info_0, procs[1])

        # Check the process exited with code 0
        self.assertEqual(self.pipe.recv(), 0)
        self.assertEqual(self.pipe.recv(), 0)

    def test_c_restart_analysis(self):
        """ Test restarting the two analyses from their respective docs. """
        for proc in self.analyses:
            self.q.put(('restart', proc['owner'], proc['access_code'], True, 1, -1))
            # Get the test tool
            self.pipe.recv()
        self.assertEqual(self.pipe.recv(), 0)
        self.assertEqual(self.pipe.recv(), 0)

    def test_d_node_analysis(self):
        for i in range(5):
            self.q.put(('analysis', self.infos[0]['owner'], self.infos[0]['access_code'], 'test', '20', None, True, -1))
            result = self.pipe.recv()
        self.assertEqual(result, 'Analysis Not Started')
