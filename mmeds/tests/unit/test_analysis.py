from unittest import TestCase
import mmeds.config as fig
import pandas as pd
from subprocess import run, CalledProcessError, TimeoutExpired
import gzip

from pathlib import Path
from mmeds.util import run_analysis
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

        # temp paths for testing demultiplexing
        cls.strip_dir = Path(cls.pheniqs_dir) / 'stripped_out/'
        cls.out_dir = Path(cls.pheniqs_dir) / 'pheniqs_out/'
        cls.log_dir = Path(cls.pheniqs_dir) / 'logs/'
        cls.target_file = '240_16_S1_L001_R1_001.fastq'

        # make paths we need
        Path(cls.pheniqs_dir).mkdir(exist_ok=True)
        cls.out_dir.mkdir(exist_ok=True)
        cls.strip_dir.mkdir(exist_ok=True)
        cls.log_dir.mkdir(exist_ok=True)
        cls.out = Path(cls.pheniqs_dir) / 'pheniqs_config_test.json'
        cls.log = Path(cls.log_dir) / 'pheniqs_report.txt'

    def test_analyses(self):
        """ Test pheniqs demultiplexing """
        run_analysis(self.test_study)
