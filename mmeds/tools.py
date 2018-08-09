from pandas import read_csv
from pathlib import Path
from subprocess import run
import os
import multiprocessing as mp

from mmeds.database import Database
from mmeds.config import get_salt, send_email


class Qiime1Analysis:
    """ A class for qiime 1.9.1 analysis of uploaded studies. """

    def __init__(self, owner, access_code):
        self.db = Database('', user='root', owner=owner, connect=False)
        self.access_code = access_code
        self.headers = [
            '#SampleID',
            'BarcodeSequence',
            'LinkerPrimerSequence',
            'Description'
        ]

        files, path = self.db.get_mongo_files(self.access_code)
        self.path = Path(path)

    def __del__(self):
        del self.db

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'source activate qiime1; validate_mapping_file.py -m {}'
        run(cmd.format(files['mapping']), shell=True, check=True)

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        metadata = self.db.get_metadata(self.access_code)
        fp = metadata.files['metadata']
        with open(fp) as f:
            mdata = read_csv(f, header=[0, 1], sep='\t')

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'
        with open(mapping_file, 'w') as f:
            f.write('\t'.join(self.headers) + '\n')
            for row_index in range(len(mdata)):
                row = []
                for header in self.headers:
                    if header == '#SampleID':
                        row.append(mdata['Specimen']['SampleID'][row_index])
                    else:
                        row.append(mdata['Specimen'][header][row_index])
                f.write('\t'.join(row) + '\n')

        # Add the mapping file to the MetaData object
        self.db.update_metadata(self.access_code, 'mapping', mapping_file)

    def split_libraries(self):
        """ Split the libraries and perform quality analysis. """
        add_path(self, 'split_output', '')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = 'source activate qiime1; split_libraries_fastq.py -o {} -i {} -b {} -m {}'
        command = cmd.format(files['split_output'], files['reads'], files['barcodes'], files['mapping'])
        run(command, shell=True, check=True)

    def pick_otu(self, reference='open'):
        """ Run the pick OTU scripts. """
        add_path(self, 'otu_output', '')
        files, path = self.db.get_mongo_files(self.access_code)

        with open(Path(path) / 'params.txt', 'w') as f:
            f.write('pick_otus:enable_rev_strand_match True\n')

        # Run the script
        cmd = 'source activate qiime1; pick_{}_reference_otus.py -o {} -i {} -p {}'
        command = cmd.format(reference,
                             files['otu_output'],
                             Path(files['split_output']) / 'seqs.fna',
                             Path(path) / 'params.txt')
        run(command, shell=True, check=True)

    def core_diversity(self):
        """ Run the core diversity analysis script. """
        add_path(self, 'diversity_output', '')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = 'source activate qiime1; core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {}'
        command = cmd.format(files['diversity_output'],
                             Path(files['otu_output']) / 'otu_table_mc2_w_tax_no_pynast_failures.biom',
                             files['mapping'],
                             Path(files['otu_output']) / 'rep_set.tre',
                             1114)
        run(command, shell=True, check=True)

    def analysis(self):
        """ Perform some analysis. """
        self.create_qiime_mapping_file()
        self.validate_mapping()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
        doc = self.db.get_metadata(self.access_code)
        send_email(doc.email, doc.owner, 'analysis', analysis_type='Qiime1', study_name=doc.study)


class Qiime2Analysis:
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype):
        self.db = Database('', user='root', owner=owner, connect=False)
        self.access_code = access_code
        self.headers = [
            '#SampleID',
            'BarcodeSequence',
            'LinkerPrimerSequence',
            'Description'
        ]

        files, path = self.db.get_mongo_files(self.access_code)
        self.path = Path(path)
        self.atype = atype.split('-')[-1]

    def __del__(self):
        del self.db

    def setup_dir(self):
        """ Setup the directory to run the analysis. """
        # Add the split directory to the MetaData object
        add_path(self, 'working_dir', '')

        files, path = self.db.get_mongo_files(self.access_code)

        run('mkdir {}'.format(files['working_dir']), shell=True, check=True)

        # Create links to the files
        run('ln {} {}'.format(files['barcodes'],
                              Path(files['working_dir']) / 'barcodes.fastq.gz'),
            shell=True, check=True)
        run('ln {} {}'.format(files['reads'],
                              Path(files['working_dir']) / 'sequences.fastq.gz'),
            shell=True, check=True)

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'source activate qiime2; validate_mapping_file.py -m {}'
        run(cmd.format(files['mapping']), shell=True, check=True)

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        metadata = self.db.get_metadata(self.access_code)
        fp = metadata.files['metadata']
        with open(fp) as f:
            mdata = read_csv(f, header=[0, 1], sep='\t')

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'
        with open(mapping_file, 'w') as f:
            f.write('\t'.join(self.headers) + '\n')
            for row_index in range(len(mdata)):
                row = []
                for header in self.headers:
                    if header == '#SampleID':
                        row.append(mdata['Specimen']['SampleID'][row_index])
                    else:
                        row.append(mdata['Specimen'][header][row_index])
                f.write('\t'.join(row) + '\n')

        # Add the mapping file to the MetaData object
        self.db.update_metadata(self.access_code, 'mapping', mapping_file)

    def qimport(self, itype='EMPSingleEndSequences'):
        """ Split the libraries and perform quality analysis. """
        files, path = self.db.get_mongo_files(self.access_code)

        # Add the split directory to the MetaData object
        self.db.update_metadata(self.access_code,
                                'working_file',
                                Path(str(files['working_dir']) + '.qza'))
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = 'source activate qiime2; qiime tools import --type {} --input-path {} --output-path {}'
        command = cmd.format(itype, files['working_dir'], files['working_file'])
        run(command, shell=True, check=True)

    def demultiplex(self):
        """ Run the core diversity analysis script. """
        # Add the otu directory to the MetaData object
        add_path(self, 'demux_file', 'qza')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = [
            'source activate qiime2;',
            ' qiime demux emp-single',
            '--i-seqs {}'.format(files['working_file']),
            '--m-barcodes-file {}'.format(files['mapping']),
            '--m-barcodes-column {}'.format(self.headers[1]),
            '--o-per-sample-sequences {}'.format(files['demux_file'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def tabulate(self):
        """ Run tabulate visualization. """
        add_path(self, 'stats_{}_visual'.format(self.atype), 'qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime metadata tabulate',
            '--m-input-file {}'.format(files['stats_{}'.format(self.atype)]),
            '--o-visualization {}'.format(files['stats_{}_visual'.format(self.atype)])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def dada2(self, p_trim_left=0, p_trunc_len=120):
        """ Run DADA2 analysis on the demultiplexed file. """
        # Index new files
        add_path(self, 'rep_seqs', 'qza')
        add_path(self, 'table_dada2', 'qza')
        add_path(self, 'stats_dada2', 'qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime dada2 denoise-single',
            '--i-demultiplexed-seqs {}'.format(files['demux_file']),
            '--p-trim-left {}'.format(p_trim_left),
            '--p-trunc-len {}'.format(p_trunc_len),
            '--o-representative-sequences {}'.format(files['rep_seqs']),
            '--o-table {}'.format(files['table_dada2']),
            '--o-denoising-stats {}'.format(files['stats_dada2'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def deblur_filter(self):
        """ Run Deblur analysis on the demultiplexed file. """
        add_path(self, 'demux_filtered', 'qza')
        add_path(self, 'demux_filter_stats', 'qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime quality-filter q-score',
            '--i-demux {}'.format(files['demux_file']),
            '--o-filtered-sequences {}'.format(files['demux_filtered']),
            '--o-filter-stats {}'.format(files['demux_filter_stats'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def deblur_denoise(self, p_trim_length=120):
        """ Run Deblur analysis on the demultiplexed file. """
        add_path(self, 'rep_seqs_deblur', 'qza')
        add_path(self, 'table_deblur', 'qza')
        add_path(self, 'stats_deblur', 'qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime deblur denoise-16S',
            '--i-demultiplexed-seqs {}'.format(files['demux_filtered']),
            '--p-trim-length {}'.format(p_trim_length),
            '--o-representative-sequences {}'.format(files['rep_seqs_deblur']),
            '--o-table {}'.format(files['table_deblur']),
            '--p-sample-stats',
            '--o-stats {}'.format(files['stats_deblur'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def deblur_visualize(self):
        """ Create visualizations from deblur analysis. """
        add_path(self, 'stats_deblur_visual', 'qzv')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime deblur visualize-stats',
            '--i-deblur-stats {}'.format(files['stats_deblur']),
            '--o-visualization {}'.format(files['stats_deblur_visual'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def analysis(self):
        """ Perform some analysis. """
        self.create_qiime_mapping_file()
        self.setup_dir()
        self.qimport()
        self.demultiplex()
        if self.atype == 'deblur':
            self.deblur_filter()
            self.deblur_denoise()
            self.deblur_visualize()
        elif self.atype == 'dada2':
            self.dada2()
            self.tabulate()
        doc = self.db.get_metadata(self.access_code)
        send_email(doc.email, doc.owner, 'analysis', analysis_type='Qiime2 ' + self.atype, study_name=doc.study)


def add_path(qiime, name, extension):
    """ Add a file or directory to the document identified by qiime.access_code. """
    new_file = Path(qiime.path) / (name + '_' + get_salt(5) + '.' + extension)
    while os.path.exists(new_file):
        new_file = Path(qiime.path) / (name + '_' + get_salt(5) + '.' + extension)
    qiime.db.update_metadata(qiime.access_code, name, new_file)


def run_qiime1(user, access_code):
    """ Run qiime analysis. """
    qa = Qiime1Analysis(user, access_code)
    qa.analysis()


def run_qiime2(user, access_code, atype):
    """ Run qiime analysis. """
    qa = Qiime2Analysis(user, access_code, atype)
    qa.analysis()


def analysis_runner(atype, user, access_code):
    """ Start running the analysis in a new process """
    if 'qiime1' in atype:
        p = mp.Process(target=run_qiime1, args=(user, access_code))
    elif 'qiime2' in atype:
        p = mp.Process(target=run_qiime2, args=(user, access_code, atype))
    p.start()
    return p
