from unittest import TestCase
import mmeds.config as fig
import pandas as pd
from subprocess import run, CalledProcessError, TimeoutExpired
import gzip

from pathlib import Path
from mmeds.util import make_pheniqs_config, strip_error_barcodes, setup_environment, validate_demultiplex
from mmeds.logging import Logger

TESTING = True


def test_strip_error_barcodes(test_case):
    """ Test the stripping of errors from pheniqs-demultiplexed read files """
    output_dir = Path(fig.TEST_STRIPPED_OUTPUT_DIR)
    if not output_dir.is_dir():
        output_dir.mkdir()

    test_dirs = fig.TEST_STRIPPED_DIRS

    # Test at three different error levels
    error_levels = [0, 1, 2, 16]
    for level in error_levels:
        # Remove old test files from dir
        for f in output_dir.glob('*'):
            f.unlink()

        strip_error_barcodes(
            level,
            fig.TEST_PHENIQS_MAPPING,
            fig.TEST_PHENIQS_DIR,
            fig.TEST_STRIPPED_OUTPUT_DIR,
            False
        )

        # Assert correct number of output files
        output_files = list(output_dir.glob('*'))
        df = pd.read_csv(Path(fig.TEST_PHENIQS_MAPPING), sep='\t', header=[0, 1], na_filter=False)
        sample_ids = df[fig.QIIME_SAMPLE_ID_CATS[0]][fig.QIIME_SAMPLE_ID_CATS[1]]
        assert len(output_files) == 2 * len(sample_ids)

        if level < 3:
            test_path = Path(test_dirs[level])
        else:
            test_path = Path(fig.TEST_PHENIQS_DIR)
        # Assert all files match their expected values
        for sample_id in sample_ids:
            f = gzip.open(output_dir / fig.FASTQ_FILENAME_TEMPLATE.format(sample_id, 1), 'rt')
            f_test = gzip.open(test_path / fig.FASTQ_FILENAME_TEMPLATE.format(sample_id, 1), 'rt')

            assert f.read() == f_test.read()

            f = gzip.open(output_dir / fig.FASTQ_FILENAME_TEMPLATE.format(sample_id, 2), 'rt')
            f_test = gzip.open(test_path / fig.FASTQ_FILENAME_TEMPLATE.format(sample_id, 2), 'rt')

            assert f.read() == f_test.read()


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
        # import pudb; pudb.set_trace()
        create_pheniqs_config(cls)
        new_env = setup_environment('pheniqs/2.1.0')

        pheniqs_demultiplex = ['pheniqs', 'mux', '--config', f'{cls.out}']
        gunzip_forward_barcodes = ['gunzip', f'{cls.for_barcodes}.gz']
        gunzip_reverse_barcodes = ['gunzip', f'{cls.rev_barcodes}.gz']

        try:
            run(pheniqs_demultiplex, capture_output=True, env=new_env, check=True, timeout=120)

        except (CalledProcessError, TimeoutExpired) as e:
            Logger.debug(e)
            print(e.output)

        try:
            run(gunzip_forward_barcodes, capture_output=True, check=True)
            run(gunzip_reverse_barcodes, capture_output=True, check=True)

        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)

        # validate one of the demultiplexed files
        validate_demultiplex(f'{cls.out_dir}/{cls.target_file}', cls.for_barcodes,
                             cls.rev_barcodes, cls.mapping, cls.log_dir, True)

        # check values in the validation log file
        file_name = cls.target_file.replace('.fastq', '_test.fastq')
        validate_log = cls.log_dir / f'{file_name}_report.log'
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

        test_strip_error_barcodes(cls)

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
