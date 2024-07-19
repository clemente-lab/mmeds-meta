from unittest import TestCase, skip
from time import sleep

from yaml import safe_load
from pathlib import Path
from datetime import datetime, timedelta

from mmeds.logging import Logger
from mmeds.database.database import Database
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

    def receive_all_pipe_output(self, time):
        pipe_results = []
        while self.pipe.poll(time):
            pipe_results.append(self.pipe.recv())
        return pipe_results

    def test_a_upload_data(self):
        """ Test uploading data through the queue """
        # Add multiple uploads from different users
        self.q.put(('upload', 'test_spawn', fig.TEST_SUBJECT_SHORT, 'human', fig.TEST_SPECIMEN_SHORT,
                    fig.TEST_USER, False, False, False))

        self.q.put(('upload', 'test_spawn_0', fig.TEST_SUBJECT_SHORT, 'human', fig.TEST_SPECIMEN_SHORT,
                    fig.TEST_USER_0, False, False, False))

        # Recieve the process info dicts from Watcher
        # Sent one at time b/c only one upload can happen at a time
        for i in [0, 1]:
            info = self.pipe.recv()
            # Drop the is alive info as it may no longer be accurate
            del info['is_alive']
            # Check they match the contents of current_processes
            with open(fig.CURRENT_PROCESSES, 'r') as f:
                procs = safe_load(f)
            for proc in procs:
                del proc['is_alive']
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
            self.q.put(('analysis', proc['owner'], proc['access_code'], 'standard_pipeline',
                        'default', 'test_analysis', None, {}, -1, False))

        Logger.info('Waiting on analysis')
        # Check the analyses are started and running simultainiously

        info = self.pipe.recv()
        info_0 = self.pipe.recv()
        self.analyses += [info, info_0]

        procs = []
        timeout = 0
        # Check they match the contents of current_processes
        with open(fig.CURRENT_PROCESSES, 'r') as f:
            while len(procs) != len(self.infos):
                if timeout > 20:
                    break

                proc = safe_load(f)
                if proc:
                    if len(proc) == len(self.infos):
                        procs = proc
                    elif proc not in procs:
                        procs += proc
                timeout += 1
                sleep(0.2)

        self.assertTrue(info == procs[0] or info == procs[1])
        self.assertTrue(info_0 == procs[0] or info_0 == procs[1])

        # Check the processes exited with code 0
        pipe_results = self.receive_all_pipe_output(5)
        self.assertEqual(pipe_results.count(0), 2)

    def test_c_restart_analysis(self):
        """ Test restarting the two analyses from their respective docs. """
        Logger.info("restarting analysis")
        for proc in self.analyses:
            self.q.put(('restart', proc['owner'], proc['access_code'], True, 1, -1))
        pipe_results = self.receive_all_pipe_output(5)
        self.assertEqual(pipe_results.count(0), len(self.analyses))

    def test_d_node_analysis(self):
        Logger.info("node analysis")
        for i in range(5):
            self.q.put(('analysis', self.infos[0]['owner'], self.infos[0]['access_code'], 'standard_pipeline',
                        'default', 'test_analysis_node', None, {}, -1, True))

        pipe_results = self.receive_all_pipe_output(5)
        Logger.debug(f"PIPE RESULTS: {pipe_results}")
        self.assertIn("Analysis Not Started", pipe_results)
        self.assertEquals(pipe_results.count(0), 4)

    @skip("uploading ids outdated")
    def test_e_generate_ids(self):
        Logger.info("generate ids")
        # Get the initial results
        for (utype, ufile) in [('aliquot', fig.TEST_ALIQUOT_UPLOAD), ('sample', fig.TEST_SAMPLE_UPLOAD)]:
            self.q.put(('upload-ids',
                        self.infos[0]['owner'],
                        self.infos[0]['access_code'],
                        ufile,
                        utype,
                        True))
            pipe_results = self.receive_all_pipe_output(5)
            self.assertIn(0, pipe_results)

    @skip("uploading ids outdated")
    def test_f_add_subject_data(self):
        # Get the initial results
        for (utype, ufile) in [('subject', fig.TEST_ADD_SUBJECT)]:
            self.q.put(('upload-ids',
                        self.infos[0]['owner'],
                        self.infos[0]['access_code'],
                        ufile,
                        utype,
                        False))
            pipe_results = self.receive_all_pipe_output(5)
            self.assertIn(0, pipe_results)

    def test_g_clean_temp_folders(self):
        """ Test code for removing temporary folders daily and on startup. """
        # Make a fake old folder that clean_temp_folders() will remove.
        day_before_yesterday = datetime.utcnow() - timedelta(days=2)
        day_before_yesterday = day_before_yesterday.strftime('%Y-%m-%d-%H:%M')
        temp_sub_dir = Path(fig.DATABASE_DIR) / 'temp_dir' / f'lab_user__{day_before_yesterday}__0x'
        temp_sub_dir.mkdir(parents=True)

        self.monitor.clean_temp_folders()
        self.assertFalse(temp_sub_dir.exists())

    def test_z_exit(self):
        Logger.error('Putting Terminate')
        self.q.put(('terminate'))
        Logger.error('Waiting on pipe')
        result = self.pipe.recv()
        Logger.error('Got {} from pipe'.format(result))
        self.assertEqual(result, 'Watcher exiting')
