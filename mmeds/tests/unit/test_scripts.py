from unittest import TestCase
import mmeds.config as fig
import pandas as pd

from pathlib import Path
from mmeds.util import make_pheniqs_config
from mmeds.util import strip_error_barcodes

TESTING = True


class ScriptsTests(TestCase):
    """ Tests of scripts """

    @classmethod
    def setUpClass(self):
        """ Set up tests """
        self.mapping = fig.TEST_MAPPING_DUAL
        self.for_reads = fig.TEST_READS_DUAL
        self.rev_reads = fig.TEST_REV_READS_DUAL
        self.for_barcodes = fig.TEST_BARCODES_DUAL
        self.rev_barcodes = fig.TEST_REV_BARCODES_DUAL
        self.tmp_dir = Path('/tmp/script_test')
        self.out = self.tmp_dir / 'pheniqs_config_test.json'
        self.out_dir = self.tmp_dir / 'pheniqs_out/'
        self.pheniqs_dir = fig.TEST_PHENIQS_DIR
        self.strip_dir = self.tmp_dir / 'stripped_out/'

    def test_make_pheniqs_config(self):
        """ Test making a pheniqs configuration .json file """
        out_s = make_pheniqs_config(
            self.for_reads,
            self.rev_reads,
            self.for_barcodes,
            self.rev_barcodes,
            self.mapping,
            self.out_dir
        )
        self.tmp_dir.mkdir(exist_ok=True)
        self.out_dir.mkdir(exist_ok=True)
        self.out.touch()
        self.out.write_text(out_s)

        assert self.out.exists()

        f = self.out.open('r')

        assert not f.readline() == ''
        assert f.readline() is not None

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

        self.tmp_dir.mkdir(exist_ok=True)
        self.strip_dir.mkdir(exist_ok=True)
        strip_error_barcodes(1, map_hash, self.pheniqs_dir, self.strip_dir)
        p_test = self.strip_dir / '{}_S1_L001_R1_001.fastq.gz'.format(map_df['#SampleID'][1])
        assert p_test.exists()
