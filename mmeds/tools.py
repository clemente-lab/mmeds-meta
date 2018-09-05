from pandas import read_csv
from pathlib import Path
from subprocess import run
from shutil import copyfile
from time import sleep
import os
import multiprocessing as mp

from mmeds.database import Database
from mmeds.config import get_salt, send_email


class Qiime1Analysis:
    """ A class for qiime 1.9.1 analysis of uploaded studies. """

    def __init__(self, owner, access_code):
        self.db = Database('', user='root', owner=owner, connect=False)
        self.access_code = access_code
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
            mdata = read_csv(f, header=[1], sep='\t')

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'

        headers = list(mdata.columns)

        si = headers.index('SampleID')
        hold = headers[0]
        headers[0] = '#SampleID'
        headers[si] = hold

        hold = headers[1]
        di = headers.index('BarcodeSequence')
        headers[1] = 'BarcodeSequence'
        headers[di] = hold

        hold = headers[2]
        di = headers.index('LinkerPrimerSequence')
        headers[2] = 'LinkerPrimerSequence'
        headers[di] = hold

        hold = headers[-1]
        di = headers.index('Description')
        headers[-1] = 'Description'
        headers[di] = hold

        with open(mapping_file, 'w') as f:
            f.write('\t'.join(headers) + '\n')
            for row_index in range(len(mdata)):
                row = []
                for header in headers:
                    if header == '#SampleID':
                        row.append(str(mdata['SampleID'][row_index]))
                    else:
                        row.append(str(mdata[header][row_index]))
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
        move_user_files(self)
        doc = self.db.get_metadata(self.access_code)
        send_email(doc.email, doc.owner, 'analysis', analysis_type='Qiime1', study_name=doc.study)


class Qiime2Analysis:
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype):
        self.db = Database('', user='root', owner=owner, connect=False)
        self.access_code = access_code
        files, path = self.db.get_mongo_files(self.access_code)
        self.path = Path(path)
        self.atype = atype.split('-')[-1]
        self.overwrite = False

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
            mdata = read_csv(f, header=[1], sep='\t')

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'

        headers = list(mdata.columns)

        si = headers.index('SampleID')
        hold = headers[0]
        headers[0] = '#SampleID'
        headers[si] = hold

        hold = headers[1]
        di = headers.index('BarcodeSequence')
        headers[1] = 'BarcodeSequence'
        headers[di] = hold

        hold = headers[2]
        di = headers.index('LinkerPrimerSequence')
        headers[2] = 'LinkerPrimerSequence'
        headers[di] = hold

        hold = headers[-1]
        di = headers.index('Description')
        headers[-1] = 'Description'
        headers[di] = hold

        with open(mapping_file, 'w') as f:
            f.write('\t'.join(headers) + '\n')
            for row_index in range(len(mdata)):
                row = []
                for header in headers:
                    if header == '#SampleID':
                        row.append(str(mdata['SampleID'][row_index]))
                    else:
                        row.append(str(mdata[header][row_index]))
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
        add_path(self, 'demux_file', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = [
            'source activate qiime2;',
            ' qiime demux emp-single',
            '--i-seqs {}'.format(files['working_file']),
            '--m-barcodes-file {}'.format(files['mapping']),
            '--m-barcodes-column {}'.format('BarcodeSequence'),
            '--o-per-sample-sequences {}'.format(files['demux_file'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def tabulate(self):
        """ Run tabulate visualization. """
        add_path(self, 'stats_{}_visual'.format(self.atype), '.qzv')
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
        add_path(self, 'rep_seqs_dada2', '.qza')
        add_path(self, 'table_dada2', '.qza')
        add_path(self, 'stats_dada2', '.qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime dada2 denoise-single',
            '--i-demultiplexed-seqs {}'.format(files['demux_file']),
            '--p-trim-left {}'.format(p_trim_left),
            '--p-trunc-len {}'.format(p_trunc_len),
            '--o-representative-sequences {}'.format(files['rep_seqs_dada2']),
            '--o-table {}'.format(files['table_dada2']),
            '--o-denoising-stats {}'.format(files['stats_dada2'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def deblur_filter(self):
        """ Run Deblur analysis on the demultiplexed file. """
        add_path(self, 'demux_filtered', '.qza')
        add_path(self, 'demux_filter_stats', '.qza')

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
        add_path(self, 'rep_seqs_deblur', '.qza')
        add_path(self, 'table_deblur', '.qza')
        add_path(self, 'stats_deblur', '.qza')

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
        add_path(self, 'stats_deblur_visual', '.qzv')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime deblur visualize-stats',
            '--i-deblur-stats {}'.format(files['stats_deblur']),
            '--o-visualization {}'.format(files['stats_deblur_visual'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def alignment_mafft(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 1"""
        add_path(self, 'alignment', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime alignment mafft',
            '--i-sequences {}'.format(files['rep_seqs_{}'.format(self.atype)]),
            '--o-alignment {}'.format(files['alignment'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def alignment_mask(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 2"""
        add_path(self, 'masked_alignment', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime alignment mask',
            '--i-alignment {}'.format(files['alignment']),
            '--o-masked-alignment {}'.format(files['masked_alignment'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def phylogeny_fasttree(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 3"""
        add_path(self, 'unrooted_tree', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime phylogeny fasttree',
            '--i-alignment {}'.format(files['masked_alignment']),
            '--o-tree {}'.format(files['unrooted_tree'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def phylogeny_midpoint_root(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 3"""
        add_path(self, 'rooted_tree', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime phylogeny midpoint-root',
            '--i-tree {}'.format(files['unrooted_tree']),
            '--o-rooted-tree {}'.format(files['rooted_tree'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def core_diversity(self, p_sampling_depth=1109):
        """ Run core diversity """
        add_path(self, 'core_metrics_results', '')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime diversity core-metrics-phylogenetic',
            '--i-phylogeny {}'.format(files['rooted_tree']),
            '--i-table {}'.format(files['table_{}'.format(self.atype)]),
            '--p-sampling-depth {}'.format(p_sampling_depth),
            '--m-metadata-file {}'.format(files['mapping']),
            '--output-dir {}'.format(files['core_metrics_results'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def alpha_diversity(self, metric='faith_pd'):
        """
        Run core diversity.
        metric : ('faith_pd' or 'evenness')
        """
        add_path(self, '{}_group_significance'.format(metric), '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime diversity alpha-group-significance',
            '--i-alpha-diversity {}'.format(Path(files['core_metrics_results']) / '{}_vector.qza'.format(metric)),
            '--m-metadata-file {}'.format(files['mapping']),
            '--o-visualization {}'.format(files['{}_group_significance'.format(metric)])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def beta_diversity(self, column='SampleDate'):
        """
        Run core diversity.
        column: Some column from the metadata file
        """
        add_path(self, 'unweighted_{}_significance'.format(column), '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime diversity beta-group-significance',
            '--i-distance-matrix {}'.format(Path(files['core_metrics_results']) / 'unweighted_unifrac_distance_matrix.qza'),
            '--m-metadata-file {}'.format(files['mapping']),
            '--m-metadata-column {}'.format(column),
            '--o-visualization {}'.format(files['unweighted_{}_significance'.format(column)]),
            '--p-pairwise'
        ]
        run(' '.join(cmd), shell=True, check=True)

    def alpha_rarefaction(self, max_depth=4000):
        """
        Create plots for alpha rarefaction.
        """
        add_path(self, 'alpha_rarefaction', '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'source activate qiime2;',
            'qiime diversity alpha-rarefaction',
            '--i-table {}'.format(files['table_{}'.format(self.atype)]),
            '--i-phylogeny {}'.format(files['rooted_tree']),
            '--p-max-depth {}'.format(max_depth),
            '--m-metadata-file {}'.format(files['mapping']),
            '--o-visualization {}'.format(files['alpha_rarefaction'])
        ]
        run(' '.join(cmd), shell=True, check=True)

    def analysis(self):
        """ Perform some analysis. """
        self.setup_dir()
        self.create_qiime_mapping_file()
        self.qimport()
        self.demultiplex()
        if self.atype == 'deblur':
            self.deblur_filter()
            self.deblur_denoise()
            self.deblur_visualize()
        elif self.atype == 'dada2':
            self.dada2()
            self.tabulate()
        self.alignment_mafft()
        self.alignment_mask()
        self.phylogeny_fasttree()
        self.phylogeny_midpoint_root()
        self.core_diversity()
        self.alpha_diversity()
        self.beta_diversity()
        self.alpha_rarefaction()
        doc = self.db.get_metadata(self.access_code)
        move_user_files(self)
        send_email(doc.email, doc.owner, 'analysis', analysis_type='Qiime2 ' + self.atype, study_name=doc.study)


def move_user_files(qiime):
    """ Move all files intended for the user to a set location. """
    add_path(qiime, 'visualizations_dir', '')
    files, path = qiime.db.get_mongo_files(qiime.access_code)
    os.mkdir(files['visualizations_dir'])
    for key in files.keys():
        f = Path(files[key])
        if '.qzv' in files[key]:
            new_file = f.name
            copyfile(files[key], Path(files['visualizations_dir']) / new_file)


def add_path(qiime, name, extension):
    """ Add a file or directory to the document identified by qiime.access_code. """
    new_file = Path(qiime.path) / (name + '_' + get_salt(5) + extension)
    while os.path.exists(new_file):
        new_file = Path(qiime.path) / (name + '_' + get_salt(5) + extension)
    qiime.db.update_metadata(qiime.access_code, name, new_file)


def run_qiime1(user, access_code):
    """ Run qiime analysis. """
    qa = Qiime1Analysis(user, access_code)
    qa.analysis()


def run_qiime2(user, access_code, atype):
    """ Run qiime analysis. """
    qa = Qiime2Analysis(user, access_code, atype)
    qa.analysis()


def test(time, atype):
    sleep(time)


def analysis_runner(atype, user, access_code):
    """ Start running the analysis in a new process """
    if 'qiime1' in atype:
        p = mp.Process(target=run_qiime1, args=(user, access_code))
    elif 'qiime2' in atype:
        p = mp.Process(target=run_qiime2, args=(user, access_code, atype))
    elif 'test' in atype:
        time = int(atype.split('-')[-1])
        p = mp.Process(target=test, args=(time, atype))
    p.start()
    return p
