from unittest import TestCase
import mmeds.config as fig
import pandas as pd
from subprocess import run, CalledProcessError
# import unittest


from pathlib import Path
from mmeds.util import make_pheniqs_config, strip_error_barcodes, setup_environment, parse_barcodes
from mmeds.logging import Logger

TESTING = True


def create_pheniqs_config(test_case):
    out_s = make_pheniqs_config(
        test_case.for_reads,
        test_case.rev_reads,
        test_case.for_barcodes,
        test_case.rev_barcodes,
        test_case.mapping,
        test_case.out_dir,
        testing=True
    )
    # test_case.tmp_dir.mkdir(exist_ok=True)
    # test_case.out_dir.mkdir(exist_ok=True)

    ### commented out
    test_case.out.touch()
    test_case.out.write_text(out_s)
    # test_case.out.chmod( 777 )

def create_barcode_mapfile(source_dir, for_barcodes, rev_barcodes, file_name, map_file):
    map_df = pd.read_csv(Path(map_file), sep='\t', header=[0, 1], na_filter=False)

    # filter mapping file down to one sample
    matched_sample = None
    for sample in map_df[('#SampleID', '#q2:types')]:
        if sample in file_name:
            matched_sample = sample
            break

    map_df.set_index(('#SampleID', '#q2:types'), inplace=True)
    map_df = map_df.filter(like=matched_sample, axis='index')

    results_dict, full_dict, barcode_ids = parse_barcodes(for_barcodes, rev_barcodes,
                                             map_df[('BarcodeSequence', 'categorical')].tolist(),
                                                          map_df[('BarcodeSequenceR', 'categorical')].tolist())
    map_df = map_df.append([map_df]*(len(barcode_ids)-1), ignore_index=True)
    # map_df.drop(columns='(#SampleID, #q2:types)', inplace=True)
    map_df.reset_index(drop=True, inplace=True)

    map_df[('#SampleID', '#q2:types')] = barcode_ids
    map_df[('#SampleID', '#q2:types')] = map_df[('#SampleID', '#q2:types')].str.split(' ', expand=True)[0]
    map_df[('#SampleID', '#q2:types')] = map_df[('#SampleID', '#q2:types')].str.replace('@', '')

    # necessary?
    map_df.set_index(('#SampleID', '#q2:types'), inplace=True)
    map_df.reset_index(inplace=True)

    map_df.to_csv(f'{source_dir}/qiime_barcode_mapfile.tsv', index=None, header=True, sep='\t')
    return map_df

### move this into utils
def validate_demultiplex(source_dir, file_name, for_barcodes, rev_barcodes, map_file, log_dir):
    """  """
    #import pudb; pudb.set_trace()

    # map_df = pd.read_csv(f'{source_dir}/qiime_barcode_mapfile.tsv', sep='\t', header=[0, 1], na_filter=False)
    #map_df[('#SampleID', '#q2:types')] = map_df[('#SampleID', '#q2:types')].str.split(' ', expand=True)[0]
    #map_df[('#SampleID', '#q2:types')] = map_df[('#SampleID', '#q2:types')].str.replace('@', '')

    #map_df.set_index(('#SampleID', '#q2:types'), inplace=True)
    #map_df.reset_index(inplace=True)
    #map_df.to_csv(f'{source_dir}/qiime_barcode_mapfile.tsv', index=None, header=True, sep='\t')

    map_df = create_barcode_mapfile(source_dir, for_barcodes, rev_barcodes, file_name, map_file)

    new_env = setup_environment('qiime/1.9.1')

    cmd1 = ['gunzip', f'{source_dir}/240_16_S1_L001_R1_001.fastq.gz']
    cmd2 = ['sed', '-n', '-i', '1~4s/^@/>/p;2~4p', f'{source_dir}/240_16_S1_L001_R1_001.fastq']


    #cmd = ['validate_demultiplexed_fasta.py', '-b', '-a',
    #        '-i', f'{source_dir}/240_16_S1_L001_R1_001.fastq',
    #        '-o', f'{log_dir}',
    #        '-m', f'{source_dir}/qiime_mapping_file_test.tsv']

    cmd = ['validate_demultiplexed_fasta.py', '-b', '-a',
            '-i', f'{source_dir}/240_16_S1_L001_R1_001.fastq',
            '-o', f'{log_dir}',
            '-m', f'{source_dir}/qiime_barcode_mapfile.tsv']

    try:
        pass
        #run(cmd1, capture_output=True, env=new_env, check=True)
        #run(cmd2, capture_output=True, env=new_env, check=True)
        #run(cmd, capture_output=True, env=new_env, check=True)
    except CalledProcessError as e:
        Logger.debug(e)
        print(e.output)
        raise e


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
        self.temp_dir = Path(self.pheniqs_dir) / 'temp/'

        Path(self.pheniqs_dir).mkdir(exist_ok=True)
        self.out_dir.mkdir(exist_ok=True)
        self.strip_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

        # self.out = Path('/home/matt/pheniqs_config_test.json')
        self.out = Path(self.pheniqs_dir) / 'pheniqs_config_test.json'

    def test_pheniqs(self):
        """ Test making a pheniqs configuration .json file """

        # import pudb; pudb.set_trace()
        create_pheniqs_config(self)
        new_env = setup_environment('pheniqs/2.0.4')

        # print(f'does out exist? {self.out.exists()}')
        # self.out = '/home/matt/pheniqs_config_test.json'
        # cmd = [f'pheniqs mux --config {self.out}']

        cmd = ['pheniqs', 'mux', '--config', f'{self.out}']
        cmd2 = ['cp', self.for_barcodes, self.temp_dir]
        cmd3 = ['cp', self.rev_barcodes, self.temp_dir]
         ### gunzip here too
        try:
            run(cmd, capture_output=True, env=new_env, check=True)
            # import pudb; pudb.set_trace()

            #run(cmd2, capture_output=True, env=new_env, check=True)
            #run(cmd3, capture_output=True, env=new_env, check=True)

        except CalledProcessError as e:
            Logger.debug(e)
            print(e.output)

        validate_demultiplex(self.pheniqs_dir, '240_16_S1_L001_R1_001.fastq.gz', self.for_barcodes, self.rev_barcodes, self.mapping, self.log_dir)

    #def test_cutadapt(self):
        """ Test making a pheniqs configuration .json file """

    #    new_env = setup_environment('qiime/1.9.1')

    #    cmd = ['qiime', 'tools', 'import',
    #            '--type', f'240_16_S1_L001_R1_001.fastq',
    #            '--input-path', f'',
    #            '--output-path', f'qiime_barcode_mapfile.tsv']

    #    cmd = ['qiime', 'cutadapt', 'demux-paired',
    #            '-i', f'{self.source_dir}/240_16_S1_L001_R1_001.fastq',
    #            '-o', f'{self.log_dir}',
    #            '-m', f'{self.source_dir}/qiime_barcode_mapfile.tsv']


#qiime tools import --type MultiplexedPairedEndBarcodeInSequence --input-path $RUN_Qiime2/import_dir --output-path $RUN_Qiime2/qiime_artifact.qza;
# qiime tools import --type EMPPairedEndSequences --input-path $RUN_Qiime2/import_dir --output-path $RUN_Qiime2/qiime_artifact.qza;


#qiime cutadapt demux-paired --i-seqs $RUN_Qiime2/qiime_artifact.qza --m-forward-barcodes-file $RUN_Qiime2/qiime_mapping_file.tsv --m-forward-barcodes-column BarcodeSequence --m-reverse-barcodes-file $RUN_Qiime2/qiime_mapping_file.tsv --m-reverse-barcodes-column BarcodeSequenceR --o-per-sample-sequences $RUN_Qiime2/demux_file.qza --o-untrimmed-sequences $RUN_Qiime2/unmatched_demuxed.qza --p-error-rate 0.3 --verbose &> $RUN_Qiime2/demux_log.txt
#
        #validate_demultiplex(self.pheniqs_dir, '240_16_S1_L001_R1_001.fastq.gz', self.for_barcodes, self.rev_barcodes, self.mapping, self.log_dir)



#def test_strip_error_barcodes(self):
#        """ Test stripping errors from demuxed fastq.gz files """
#        map_df = pd.read_csv(Path(self.mapping), sep='\t', header=[0], na_filter=False)
#        map_hash = {}
#
#        for i in range(len(map_df['#SampleID'])):
#            # for testing
#            break
#            if i > 0:
#                map_hash[map_df['#SampleID'][i]] = \
#                    (
#                        map_df['BarcodeSequence'][i],
#                        map_df['BarcodeSequenceR'][i]
#                    )
#
        # self.tmp_dir.mkdir(exist_ok=True)
        # self.strip_dir.mkdir(exist_ok=True)
        #strip_error_barcodes(1, map_hash, self.pheniqs_dir, self.strip_dir)
        #p_test = self.strip_dir / '{}_S1_L001_R1_001.fastq.gz'.format(map_df['(#SampleID, #q2:types)'][1])
        # assert p_test.exists()
