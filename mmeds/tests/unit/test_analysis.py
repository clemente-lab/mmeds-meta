from unittest import TestCase
import mmeds.config as fig
import pandas as pd
from subprocess import run, CalledProcessError, TimeoutExpired
import gzip

from pathlib import Path
from mmeds.util import run_analysis, setup_environment
from mmeds.logging import Logger
from mmeds.summary import summarize_qiime
from mmeds.logging import Logger

TESTING = True


class AnalysisTests(TestCase):
    """ Tests of scripts """
    @classmethod
    def setUpClass(cls):
        """ Set up tests """
        # paths in config.py
        cls.mapping = fig.TEST_MAPPING_DUAL
        cls.for_reads = fig.TEST_READS_DUAL
        cls.rev_reads = fig.TEST_REV_READS_DUAL
        cls.for_barcodes = fig.TEST_BARCODES_DUAL
        cls.rev_barcodes = fig.TEST_REV_BARCODES_DUAL
        cls.test_study = fig.TEST_STUDY
        print("ho")


    def test_analyses(self):
        """ Test pheniqs demultiplexing """
        print("hi")
        # import pudb; pudb.set_trace()

        # run_analysis(self.test_study, 'qiime2')
        # summarize_qiime(f'{self.test_study}/Qiime2_0', 'qiime2', testing=True)
        new_env = setup_environment('jupyter')

        summary = f'{self.test_study}/summary'
        cmd = f'cd {summary}; jupyter nbconvert --to latex --template mod_revtex.tplx'
        cmd += ' {}.ipynb'.format('mkstapylton@gmail.com-mattS-qiime2')
        # Don't let the cells timeout, some will take a long time to process
        cmd += ' --execute --ExecutePreprocessor.timeout=-1'
        cmd += ' --ExecutePreprocessor.kernel_name="jupyter"'

        try:
            output = run(cmd, check=True, env=new_env, shell=True, capture_output=True)
            print(output)
            Logger.debug(output)

        except:
            print('hi')



