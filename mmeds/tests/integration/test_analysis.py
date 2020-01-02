from mmeds import spawn
from mmeds.authentication import add_user, remove_user
from mmeds.summary import summarize_qiime
from mmeds.util import log
from unittest import TestCase
from pathlib import Path
from time import sleep
from datetime import datetime
import multiprocessing as mp
import mmeds.config as fig
import mmeds.secrets as sec


class AnalysisTests(TestCase):
    testing = True
    count = 0

    @classmethod
    def setUpClass(self):
        print('Setting up analysis tests')
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=self.testing)
        self.code = 'test_analysis'
        self.files = None
        self.path = None
        self.q = mp.Queue()
        self.manager = mp.Manager()
        self.current_processes = self.manager.list()
        pipe_ends = mp.Pipe()
        self.pipe = pipe_ends[0]
        self.watcher = spawn.Watcher(self.q, pipe_ends[1], mp.current_process(), self.testing)
        self.watcher.start()
        test_files = {'for_reads': fig.TEST_READS, 'barcodes': fig.TEST_BARCODES}
        self.q.put(('upload', 'test_spawn', fig.TEST_SUBJECT_SHORT, fig.TEST_SPECIMEN_SHORT,
                    fig.TEST_USER, 'single_end', 'single', test_files, False, False))

        # Assert upload has started
        upload = self.pipe.recv()
        print(upload)
        self.code = upload['study_code']

        # Wait for upload to complete succesfully
        assert self.pipe.recv() == 0

    @classmethod
    def tearDownClass(self):
        remove_user(fig.TEST_USER, testing=self.testing)
        self.watcher.terminate()

    def summarize(self, count, tool):
        summarize_qiime(tool.path, tool)
        self.assertTrue((tool.path / 'summary').is_dir())

    def test_qiime1_with_children(self):
        print('Running qiime1 tests')
        log('after data modification')
        p = spawn.spawn_analysis('qiime2', 'dada2', fig.TEST_USER, self.code,
                                 Path(fig.TEST_CONFIG_SUB).read_text(),
                                 self.testing)
        #$self.q.put(('analysis', fig.TEST_USER, self.code, 'qiime1', 'closed', Path(fig.TEST_CONFIG_SUB), 1))
        print('spawned test process {}:{}'.format(p.name, p.pid))

        # Get the info on the analysis
        analysis = self.pipe.recv()
        print(analysis)

        code = analysis['analysis_code']
        # Check it failed
        self.assertEqual(self.pipe.recv(), 1)
        while p.is_alive():
            print('{}: Waiting on process: {}:{}'.format(datetime.now(), p.name, p.pid))
            print('{}, {}'.format(p.is_alive(), p.exitcode))
            sleep(20)
        log('analysis finished')
        self.assertTrue((Path(self.path) /
                         'Qiime2_0/summary/mmeds.tester@outlook.com-{}-{}.pdf'.format(fig.TEST_USER,
                                                                                      'qiime2')).is_file())
        for child in p.children:
            while child.is_alive():
                print('{}: Waiting on process: {}'.format(datetime.now(), child.name))
                sleep(20)
            self.assertEqual(child.exitcode, 0)
        self.assertEqual(p.exitcode, 0)
        self.summarize(0, p)
        print('Still exists {}'.format(p.path.is_dir()))

    def test_qiime2_with_restarts(self):
        return
        print('running qiime2 tests')
        self.q.put(('analysis', fig.TEST_USER, self.code, 'qiime2', 'dada2', Path(fig.TEST_CONFIG), 1))

        # Get the info on the analysis
        analysis = self.pipe.recv()
        print(analysis)

        code = analysis['analysis_code']
        # Check it failed
        self.assertEqual(self.pipe.recv(), 1)

        # Test restarting from each checkpoint
        for i in range(1, 5):
            self.q.put(('restart', fig.TEST_USER, code, i, i + 1))
            analysis = self.pipe.recv()
            print(analysis)
            exitcode = self.pipe.recv()
            if i < 4:
                self.assertEqual(exitcode, 1)

        analysis = self.pipe.recv()
        print(analysis)
        exitcode = self.pipe.recv()

        self.assertEqual(exitcode, 0)
        self.assertTrue((Path(self.path) /
                         'Qiime2_0/summary/mmeds.tester@outlook.com-{}-{}.pdf'.format(fig.TEST_USER,
                                                                                      'qiime2')).is_file())
