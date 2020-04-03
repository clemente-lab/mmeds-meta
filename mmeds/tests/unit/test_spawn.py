from unittest import TestCase
from time import sleep

from yaml import safe_load

from mmeds.log import MMEDSLog
import mmeds.config as fig
import mmeds.spawn as sp
import multiprocessing as mp

import multiprocessing_logging as mpl
mpl.install_mp_handler()

testing = True

logger = MMEDSLog('test_spawn-debug').logger

q = mp.Queue()
pipe_ends = mp.Pipe()
watcher = sp.Watcher(q, pipe_ends[1], mp.current_process(), testing)
watcher.start()


class SpawnTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        self.manager = mp.Manager()
        self.current_processes = self.manager.list()
        self.pipe = pipe_ends[0]
        self.infos = []
        self.analyses = []

    def test_a_upload_data(self):
        """ Test uploading data through the queue """
        test_files = {'for_reads': fig.TEST_READS, 'barcodes': fig.TEST_BARCODES}

        # Add multiple uploads from different users
        q.put(('upload', 'test_spawn', fig.TEST_SUBJECT_SHORT, 'human', fig.TEST_SPECIMEN_SHORT,
               fig.TEST_USER, 'single_end', 'single_barcodes', test_files, False, False))

        q.put(('upload', 'test_spawn_0', fig.TEST_SUBJECT_SHORT, 'human', fig.TEST_SPECIMEN_SHORT,
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
        logger.info('Upload data finished')

    def test_b_start_analysis(self):
        """ Test starting analysis through the queue """
        for proc in self.infos:
            q.put(('analysis', proc['owner'], proc['access_code'], 'test', '20', None, True, -1))

        logger.info('Waiting on analysis')
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
            q.put(('restart', proc['owner'], proc['access_code'], True, 1, -1))
            # Get the test tool
            self.pipe.recv()
        self.assertEqual(self.pipe.recv(), 0)
        self.assertEqual(self.pipe.recv(), 0)

    def test_d_node_analysis(self):
        return
        for i in range(3):
            q.put(('analysis', self.infos[0]['owner'], self.infos[0]['access_code'], 'test', '20', None, True, -1))
        for i in range(3):
            result = self.pipe.recv()
            logger.error('{} result"{}"'.format(i, result))
        self.assertEqual(result, 'Analysis Not Started')

    def test_z_exit(self):
        q.put(('terminate'))
        self.assertEqual(self.pipe.recv(), 'Watcher exiting')
