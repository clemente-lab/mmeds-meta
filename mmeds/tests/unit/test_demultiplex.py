from unittest import TestCase
import mmeds.config as fig
import pandas as pd
from subprocess import run, CalledProcessError
# import unittest


from pathlib import Path
from mmeds.util import make_pheniqs_config, strip_error_barcodes, setup_environment, validate_demultiplex
from mmeds.logging import Logger

TESTING = True


def create_pheniqs_config(test_case):
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
    def setUpClass(self):
        """ Set up tests """
        # paths in config.py
        self.mapping = fig.TEST_MAPPING_DUAL
        self.for_reads = fig.TEST_READS_DUAL
        self.rev_reads = fig.TEST_REV_READS_DUAL
        self.for_barcodes = fig.TEST_BARCODES_DUAL
        self.rev_barcodes = fig.TEST_REV_BARCODES_DUAL
        self.pheniqs_dir = fig.TEST_PHENIQS_DIR

        # temp paths for testing demultiplexing
        self.strip_dir = Path(self.pheniqs_dir) / 'stripped_out/'
        self.out_dir = Path(self.pheniqs_dir) / 'pheniqs_out/'
        self.log_dir = Path(self.pheniqs_dir) / 'logs/'
        self.target_file = '240_16_S1_L001_R1_001.fastq'

        # make paths we need
        Path(self.pheniqs_dir).mkdir(exist_ok=True)
        self.out_dir.mkdir(exist_ok=True)
        self.strip_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        self.out = Path(self.pheniqs_dir) / 'pheniqs_config_test.json'
        self.log = Path(self.log_dir) / 'pheniqs_report.txt'

    def test_pheniqs(self):
        """ Test pheniqs demultiplexing """
        create_pheniqs_config(self)
        new_env = setup_environment('pheniqs/2.1.0')

        gunzip_forward_barcodes = ['gunzip', f'{self.for_barcodes}.gz']
        gunzip_reverse_barcodes = ['gunzip', f'{self.rev_barcodes}.gz']
        pheniqs_demultiplex = ['pheniqs', 'mux', '--config', f'{self.out}']

        try:
            run(pheniqs_demultiplex, capture_output=True, env=new_env, check=True)
            run(gunzip_forward_barcodes, capture_output=True, check=True)
            run(gunzip_reverse_barcodes, capture_output=True, check=True)

        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)

        # validate one of the demultiplexed files
        validate_demultiplex(f'{self.out_dir}/{self.target_file}', self.for_barcodes,
                             self.rev_barcodes, self.mapping, self.log_dir, True)

        # check values in the validation log file
        validate_log = self.log_dir / f'{self.target_file}_report.log'
        log_df = pd.read_csv(validate_log, sep=':', skiprows=[0], names=['stat', 'value'])
        log_df.set_index('stat', inplace=True)
        log_df = log_df.T

        self.assertEqual(log_df['Percent duplicate labels']['value'], 0)
        self.assertEqual(log_df['Percent QIIME-incompatible fasta labels']['value'], 0)

        # If it's 1, no SampleIDs were found
        # This should be a value between 0 and 1, representing the percentage of exact match barcodes
        self.assertNotEqual(log_df['Percent of labels that fail to map to SampleIDs']['value'], 1)
        self.assertEqual(log_df['Percent of sequences with invalid characters']['value'], 0)
        self.assertEqual(log_df['Percent of sequences with barcodes detected']['value'], 0)
        self.assertEqual(
            log_df['Percent of sequences with barcodes detected at the beginning of the sequence']['value'], 0)

        self.assertEqual(log_df['Percent of sequences with primers detected']['value'], 0)
        self.assertTrue('All SampleIDs found in sequence labels.' in log_df.columns)

        gzip1 = ['gzip', f'{self.for_barcodes}']
        gzip2 = ['gzip', f'{self.rev_barcodes}']
        try:
            # pass
            run(gzip1, capture_output=True, check=True)
            run(gzip2, capture_output=True, check=True)
        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)

    def test_strip_error_barcodes(self):
        """ Test stripping errors from demuxed fastq.gz files """
        map_df = pd.read_csv(Path(self.mapping), sep='\t', header=[0], na_filter=False)
        map_hash = {}

        for i in range(len(map_df['#SampleID'])):
            if i > 0:
                map_hash[map_df['#SampleID'][i]] = \
                    (
                        map_df['BarcodeSequence'][i],
                        map_df['BarcodeSequenceR'][i]
                    )

        strip_error_barcodes(1, map_hash, self.out_dir, self.strip_dir)
        p_test = self.strip_dir / '{}_S1_L001_R1_001.fastq.gz'.format(map_df['#SampleID'][1])
        assert p_test.exists()

    @classmethod
    def tearDownClass(self):
        """ Set up tests """
        # cleanup demultiplexed files.
        remove_test_dir = ['rm', '-rf', f'{self.out_dir}']
        try:
            run(remove_test_dir, capture_output=True, check=True)

        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)
