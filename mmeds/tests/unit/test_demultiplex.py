from unittest import TestCase
import mmeds.config as fig
import pandas as pd
from subprocess import run, CalledProcessError

from pathlib import Path
from mmeds.util import make_pheniqs_config, strip_error_barcodes, setup_environment, validate_demultiplex
from mmeds.logging import Logger

TESTING = True


def create_pheniqs_config(test_case):
    ''' creates a config file for pheniqs demultiplexing'''
    out_s = make_pheniqs_config(
        test_case.for_reads + '.gz',
        test_case.rev_reads + '.gz',
        test_case.for_barcodes + '.gz',
        test_case.rev_barcodes + '.gz',
        test_case.mapping,
        test_case.out_dir,
        testing=True
    )

    test_case.out.touch()
    test_case.out.write_text(out_s)


class DemultiplexTests(TestCase):
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
        cls.pheniqs_dir = fig.TEST_PHENIQS_DIR

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

    def test_pheniqs(cls):
        """ Test pheniqs demultiplexing """
        create_pheniqs_config(cls)
        new_env = setup_environment('pheniqs/2.1.0')

        gunzip_forward_barcodes = ['gunzip', f'{cls.for_barcodes}.gz']
        gunzip_reverse_barcodes = ['gunzip', f'{cls.rev_barcodes}.gz']
        pheniqs_demultiplex = ['pheniqs', 'mux', '--config', f'{cls.out}']

        try:
            run(pheniqs_demultiplex, capture_output=True, env=new_env, check=True)
            run(gunzip_forward_barcodes, capture_output=True, check=True)
            run(gunzip_reverse_barcodes, capture_output=True, check=True)

        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)

        # validate one of the demultiplexed files
        validate_demultiplex(f'{cls.out_dir}/{cls.target_file}', cls.for_barcodes,
                             cls.rev_barcodes, cls.mapping, cls.log_dir, True)

        # check values in the validation log file
        validate_log = cls.log_dir / f'{cls.target_file}_report.log'
        log_df = pd.read_csv(validate_log, sep=':', skiprows=[0], names=['stat', 'value'])
        log_df.set_index('stat', inplace=True)
        log_df = log_df.T

        cls.assertEqual(log_df['Percent duplicate labels']['value'], 0)
        cls.assertEqual(log_df['Percent QIIME-incompatible fasta labels']['value'], 0)

        # If it's 1, no SampleIDs were found
        # This should be a value between 0 and 1, representing the percentage of exact match barcodes
        cls.assertNotEqual(log_df['Percent of labels that fail to map to SampleIDs']['value'], 1)
        cls.assertEqual(log_df['Percent of sequences with invalid characters']['value'], 0)
        cls.assertEqual(log_df['Percent of sequences with barcodes detected']['value'], 0)
        cls.assertEqual(
            log_df['Percent of sequences with barcodes detected at the beginning of the sequence']['value'], 0)

        cls.assertEqual(log_df['Percent of sequences with primers detected']['value'], 0)
        cls.assertTrue('All SampleIDs found in sequence labels.' in log_df.columns)

        gzip1 = ['gzip', f'{cls.for_barcodes}']
        gzip2 = ['gzip', f'{cls.rev_barcodes}']
        try:
            # pass
            run(gzip1, capture_output=True, check=True)
            run(gzip2, capture_output=True, check=True)
        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)

    @classmethod
    def tearDownClass(cls):
        """ Set up tests """
        # cleanup demultiplexed files.
        remove_test_dir = ['rm', '-rf', f'{cls.out_dir}']
        try:
            run(remove_test_dir, capture_output=True, check=True)

        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)