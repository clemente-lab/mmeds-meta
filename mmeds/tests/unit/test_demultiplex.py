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
        self.mapping = fig.TEST_MAPPING_DUAL
        self.for_reads = fig.TEST_READS_DUAL
        self.rev_reads = fig.TEST_REV_READS_DUAL
        self.for_barcodes = fig.TEST_BARCODES_DUAL
        self.rev_barcodes = fig.TEST_REV_BARCODES_DUAL
        self.pheniqs_dir = fig.TEST_PHENIQS_DIR
        self.strip_dir = Path(self.pheniqs_dir) / 'stripped_out/'
        self.out_dir = Path(self.pheniqs_dir) / 'pheniqs_out/'
        self.log_dir = Path(self.pheniqs_dir) / 'logs/'
        self.target_file = '240_16_S1_L001_R1_001.fastq'
        self.temp_dir = Path(self.pheniqs_dir) / 'temp/'

        Path(self.pheniqs_dir).mkdir(exist_ok=True)
        self.out_dir.mkdir(exist_ok=True)
        self.strip_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

        # self.out = Path('/home/matt/pheniqs_config_test.json')
        self.out = Path(self.pheniqs_dir) / 'pheniqs_config_test.json'
        self.log = Path(self.log_dir) / 'pheniqs_report.txt'

    def test_pheniqs(self):
        """ Test making a pheniqs configuration .json file """
        # import pudb; pudb.set_trace()
        create_pheniqs_config(self)
        new_env = setup_environment('pheniqs/2.1.0')

        gunzip_forward_barcodes = ['gunzip', f'{self.for_barcodes}.gz']
        gunzip_reverse_barcodes = ['gunzip', f'{self.rev_barcodes}.gz']
        pheniqs_demultiplex = ['pheniqs', 'mux', '--config', f'{self.out}']

        try:
            pass
            run(pheniqs_demultiplex, capture_output=True, env=new_env, check=True)
            run(gunzip_forward_barcodes, capture_output=True, check=True)
            run(gunzip_reverse_barcodes, capture_output=True, check=True)

        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)

        validate_demultiplex(self.out_dir, f'{self.target_file}', self.for_barcodes,
                             self.rev_barcodes, self.mapping, self.log_dir)
        validate_log = self.log_dir / f'{self.target_file}_report.log'
        log_df = pd.read_csv(validate_log, sep=':', skiprows=[0], names=['stat', 'value'])
        log_df.set_index('stat', inplace=True)
        log_df = log_df.T

        self.assertEqual(log_df['Percent duplicate labels']['value'], 0)
        self.assertEqual(log_df['Percent QIIME-incompatible fasta labels']['value'], 0)
        self.assertNotEqual(log_df['Percent of labels that fail to map to SampleIDs']['value'], 1)
        self.assertEqual(log_df['Percent of sequences with invalid characters']['value'], 0)
        self.assertEqual(log_df['Percent of sequences with barcodes detected']['value'], 0)
        self.assertEqual(
            log_df['Percent of sequences with barcodes detected at the beginning of the sequence']['value'], 0)

        self.assertEqual(log_df['Percent of sequences with primers detected']['value'], 0)
        self.assertTrue('All SampleIDs found in sequence labels.' in log_df.columns)

        cmd5 = ['gzip', f'{self.for_barcodes}']
        cmd6 = ['gzip', f'{self.rev_barcodes}']
        try:
            pass
            run(cmd5, capture_output=True, check=True)
            run(cmd6, capture_output=True, check=True)
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
        # cleanup
        remove_test_dir = ['rm', '-rf', f'{self.out_dir}']
        try:
            run(remove_test_dir, capture_output=True, check=True)

        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)
