from unittest import TestCase
from time import sleep

from yaml import safe_load

from mmeds.logging import Logger
import mmeds.config as fig
import mmeds.spawn as sp

testing = True


class SpawnTests(TestCase):
    """ Tests of top-level functions """

    @classmethod
    def setUpClass(self):
        self.monitor = sp.Watcher()
        self.monitor.connect()
        self.q = self.monitor.get_queue()
        self.pipe = self.monitor.get_pipe()
        self.infos = []
        self.analyses = []

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
        Logger.info('Upload data finished')

    def test_b_start_analysis(self):
        """ Test starting analysis through the queue """
        for proc in self.infos:
            self.q.put(('analysis', proc['owner'], proc['access_code'], 'test', '20', None, True, -1))

        Logger.info('Waiting on analysis')
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
        for i in range(3):
            self.q.put(('analysis', self.infos[0]['owner'], self.infos[0]['access_code'], 'test', '20', None, True, -1))
        for i in range(3):
            result = self.pipe.recv()
            Logger.error('{} result"{}"'.format(i, result))
        self.assertEqual(result, 'Analysis Not Started')

    def test_z_exit(self):
        Logger.error('Putting Terminate')
        self.q.put(('terminate'))
        Logger.error('Waiting on pipe')
        result = self.pipe.recv()
        Logger.error('Got {} from pipe'.format(result))
        self.assertEqual(result, 'Watcher exiting')
