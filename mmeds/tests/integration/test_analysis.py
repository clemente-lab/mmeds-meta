from mmeds import spawn
from mmeds.authentication import add_user, remove_user
from mmeds.summary import summarize_qiime
from mmeds.util import log, load_config
from mmeds.database import Database
from mmeds.tools.qiime1 import Qiime1
from unittest import TestCase
from pathlib import Path
from time import sleep
from datetime import datetime
import multiprocessing as mp
import mmeds.config as fig
import mmeds.secrets as sec

"""
NOTE: If there are 'return' statements at the top of functions is just to
prevent those tests from running as each test takes a long time and not all
are relevant to the current code section being modified.
"""


class AnalysisTests(TestCase):
    testing = True
    count = 0

    @classmethod
    def setUpClass(self):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=self.testing)
        self.files = None
        self.path = None
        self.q = mp.Queue()
        self.manager = mp.Manager()
        self.current_processes = self.manager.list()
        pipe_ends = mp.Pipe()
        self.pipe = pipe_ends[0]
        self.watcher = spawn.Watcher(self.q, pipe_ends[1], mp.current_process(), self.testing)
        self.watcher.start()
        self.code = fig.TEST_CODE

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=self.testing)
        self.watcher.terminate()

    def summarize(self, count, tool):
        summarize_qiime(tool.path, tool)
        self.assertTrue((tool.path / 'summary').is_dir())

    def test_qiime1(self):
        return
        self.q.put(('analysis', fig.TEST_USER, self.code, 'qiime1', 'closed', Path(fig.TEST_CONFIG), True, -1))
        got = self.pipe.recv()
        print(got)

        # Check for success
        self.assertEqual(self.pipe.recv(), 0)

    def test_qiime1_with_children(self):
        return
        log('after data modification')
        with Database('.', owner=fig.TEST_USER, testing=self.testing) as db:
            files, path = db.get_mongo_files(self.code)
        config = load_config(Path(fig.TEST_CONFIG_SUB), files['metadata'])

        p = Qiime1(fig.TEST_USER, self.code, 'qiime1', 'closed', config, self.testing)
        p.start()

        while p.is_alive():
            print('{}: Waiting on process: {}:{}'.format(datetime.now(), p.name, p.pid))
            sleep(20)
        log('analysis finished')
        self.assertEqual(p.exitcode, 0)
        self.assertTrue((Path(p.doc.path) /
                         'summary/mmeds.tester@outlook.com-{}-{}.pdf'.format(fig.TEST_USER,
                                                                             'qiime1')).is_file())
        for child in p.children:
            while child.is_alive():
                print('{}: Waiting on process: {}'.format(datetime.now(), child.name))
                sleep(20)
            self.assertEqual(child.exitcode, 0)
        self.assertEqual(p.exitcode, 0)
        self.summarize(0, p)

    def test_qiime2(self):
        self.q.put(('analysis', fig.TEST_USER, self.code, 'qiime2', 'dada2', Path(fig.TEST_CONFIG), True, -1))
        # Get the info on the analysis
        self.pipe.recv()

        # Check it succeeded
        self.assertEqual(self.pipe.recv(), 0)

    def test_qiime2_with_restarts(self):
        return
        print('start initial analysis')
        self.q.put(('analysis', fig.TEST_USER, self.code, 'qiime2', 'dada2', Path(fig.TEST_CONFIG), True, 1))

        # Get the info on the analysis
        analysis = self.pipe.recv()
        code = analysis['access_code']

        # Check it failed
        self.assertEqual(self.pipe.recv(), 1)

        print('Initial analysis finished')
        # Test restarting from each checkpoint
        for i in range(1, 5):
            self.q.put(('restart', fig.TEST_USER, code, i, i + 1))
            print('restart {} queued'.format(i))
            analysis = self.pipe.recv()
            exitcode = self.pipe.recv()
            if i < 4:
                self.assertEqual(exitcode, 1)

        self.assertEqual(exitcode, 0)
        self.assertTrue((Path(analysis['path']) /
                         'summary/mmeds.tester@outlook.com-{}-{}.pdf'.format(fig.TEST_USER,
                                                                             'qiime2')).is_file())
