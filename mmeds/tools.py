from pathlib import Path
from subprocess import run, CalledProcessError, PIPE
from shutil import copyfile
from time import sleep
from pandas import read_csv
from shutil import rmtree
from glob import glob
from collections import defaultdict

import os
import multiprocessing as mp

from mmeds.database import Database
from mmeds.config import get_salt, JOB_TEMPLATE, STORAGE_DIR
from mmeds.mmeds import send_email, log
from mmeds.authentication import get_email
from mmeds.error import AnalysisError
from mmeds.summarize import summarize_qiime1


class Tool:
    """ The base class for tools used by mmeds """

    def __init__(self, owner, access_code, atype, testing, threads=10, analysis=True):
        log('Start analysis')
        self.db = Database('', owner=owner, testing=testing)
        self.access_code = access_code
        files, path = self.db.get_mongo_files(self.access_code)
        self.testing = testing
        self.jobtext = []
        self.owner = owner
        if testing:
            self.num_jobs = 2
        else:
            self.num_jobs = threads
        self.atype = atype.split('-')[1]
        self.sampling_depth = 1114  # This should be chosen intellegently
        self.analysis = analysis
        self.path, self.run_id = self.setup_dir(path)

        # Add the split directory to the MetaData object
        self.add_path('analysis{}'.format(self.run_id), '')
        self.columns = []

    def __del__(self):
        del self.db

    def setup_dir(self, path):
        """ Setup the directory to run the analysis. """
        run_id = 0
        new_dir = Path(path) / 'analysis{}'.format(run_id)
        while os.path.exists(new_dir):
            run_id += 1
            new_dir = Path(path) / 'analysis{}'.format(run_id)
            log('Run analysis')
        if self.analysis:
            files, path = self.db.get_mongo_files(self.access_code)
            run('mkdir {}'.format(new_dir), shell=True, check=True)

            # Create links to the files
            run('ln {} {}'.format(files['barcodes'],
                                  new_dir / 'barcodes.fastq.gz'),
                shell=True, check=True)
            run('ln {} {}'.format(files['reads'],
                                  new_dir / 'sequences.fastq.gz'),
                shell=True, check=True)
            run('ln {} {}'.format(files['metadata'],
                                  new_dir / 'metadata.tsv'),
                shell=True, check=True)
        else:
            run_id -= 1
            new_dir = Path(path) / 'analysis{}'.format(run_id)
            log("Skip analysis")
        log("Analysis directory is {}".format(new_dir))
        return new_dir, str(run_id)

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(files['mapping'], self.path)
        self.jobtext.append(cmd)

    def get_job_params(self):
        params = {
            'walltime': '48:00',
            'jobname': self.owner + '_' + self.run_id,
            'nodes': self.num_jobs,
            'memory': 1000,
            'jobid': self.path / self.run_id,
            'queue': 'expressalloc'
        }
        return params

    def wait_on_job(self, job_id):
        """
        Wait until the specified job is finished.
        Then return.
        """
        running = True
        while running:
            # Set running to false
            running = False
            output = run('bjobs', stdout=PIPE).stdout.decode('utf-8').split('\n')
            for job in output:
                # If the job is found set it back to true
                if str(job_id) in job:
                    running = True
            # Wait thirty seconds to check again
            sleep(30)
        return

    def move_user_files(self):
        """ Move all files intended for the user to a set location. """
        try:
            self.add_path('visualizations_dir', '')
            files, path = self.db.get_mongo_files(self.access_code)
            os.mkdir(files['visualizations_dir'])
            for key in files.keys():
                f = Path(files[key])
                if '.qzv' in files[key]:
                    new_file = f.name
                    copyfile(files[key], Path(files['visualizations_dir']) / new_file)
        except FileNotFoundError as e:
            raise AnalysisError(e.args[0])

    def add_path(self, name, extension):
        """ Add a file or directory to the document identified by qiime.access_code. """
        new_file = Path(self.path) / (str(name) + '_' + get_salt(5) + extension)
        while os.path.exists(new_file):
            new_file = Path(self.path) / (str(name) + '_' + get_salt(5) + extension)
        self.db.update_metadata(self.access_code, str(name), new_file)

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        metadata = self.db.get_metadata(self.access_code)
        fp = metadata.files['metadata']
        mdata = read_csv(fp, header=1, skiprows=[2, 3, 4], sep='\t')
        self.columns = list(mdata.columns)

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'

        headers = list(mdata.columns)

        di = headers.index('RawDataID')
        hold = headers[0]
        headers[0] = '#SampleID'
        headers[di] = hold

        di = headers.index('SampleID')
        hold = headers[3]
        headers[3] = 'MmedsSampleID'
        headers[di] = hold

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
                        row.append(str(mdata['RawDataID'][row_index]))
                    elif header == 'MmedsSampleID':
                        row.append(str(mdata['SampleID'][row_index]))
                    else:
                        row.append(str(mdata[header][row_index]))
                f.write('\t'.join(row) + '\n')

        # Add the mapping file to the MetaData object
        self.db.update_metadata(self.access_code, 'mapping', mapping_file)


class Qiime1(Tool):
    """ A class for qiime 1.9.1 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, testing):
        super().__init__(owner, access_code, atype, testing)
        if testing:
            self.jobtext.append('source activate qiime1;')
        else:
            self.jobtext.append('module load qiime/1.9.1;')

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(files['mapping'], self.path)
        self.jobtext.append(cmd)

    def split_libraries(self):
        """ Split the libraries and perform quality analysis. """
        self.add_path('split_output', '')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = 'split_libraries_fastq.py -o {} -i {} -b {} -m {};'
        command = cmd.format(files['split_output'], files['reads'], files['barcodes'], files['mapping'])
        self.jobtext.append(command)

    def pick_otu(self):
        """ Run the pick OTU scripts. """
        self.add_path('otu_output', '')
        files, path = self.db.get_mongo_files(self.access_code)

        with open(Path(path) / 'params.txt', 'w') as f:
            f.write('pick_otus:enable_rev_strand_match True\n')

        # Run the script
        cmd = 'pick_{}_reference_otus.py -a -O {} -o {} -i {} -p {};'
        command = cmd.format(self.atype,
                             self.num_jobs,
                             files['otu_output'],
                             Path(files['split_output']) / 'seqs.fna',
                             Path(path) / 'params.txt')
        self.jobtext.append(command)

    def core_diversity(self):
        """ Run the core diversity analysis script. """
        self.add_path('diversity_output', '')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = 'core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {};'
        if self.atype == 'open':
            command = cmd.format(files['diversity_output'],
                                 Path(files['otu_output']) / 'otu_table_mc2_w_tax_no_pynast_failures.biom',
                                 files['mapping'],
                                 Path(files['otu_output']) / 'rep_set.tre',
                                 self.sampling_depth)
        else:
            command = cmd.format(files['diversity_output'],
                                 Path(files['otu_output']) / 'otu_table.biom',
                                 files['mapping'],
                                 Path(files['otu_output']) / '97_otus.tree',
                                 self.sampling_depth)

        self.jobtext.append(command)

    def sanity_check(self):
        """ Check that counts match after split_libraries and pick_otu. """
        log('Job Text')
        log('\n'.join(self.jobtext))
        files, path = self.db.get_mongo_files(self.access_code)

        cmd = '{} count_seqs.py -i {}'.format(self.jobtext[1],
                                              Path(files['split_output']) / 'seqs.fna')
        log('Run command: {}'.format(cmd))
        output = run(cmd, shell=True, check=True, stdout=PIPE)
        out = output.stdout.decode('utf-8')
        log('Output: {}'.format(out))
        initial_count = int(out.split('\n')[1].split(' ')[0])

        with open(Path(files['diversity_output']) / 'biom_table_summary.txt') as f:
            lines = f.readlines()
            log('Check lines: {}'.format(lines))
            final_count = int(lines[2].split(':')[-1].strip().replace(',', ''))
        if abs(initial_count - final_count) > 0.05 * (initial_count + final_count):
            message = 'Large difference ({}) between initial and final counts'
            log('Raise analysis error')
            raise AnalysisError(message.format(initial_count - final_count))
        log('Sanity check completed successfully')

    def summarize(self):
        """
        Create summary of analysis results
        """
        log('Run summarize')
        files, path = self.db.get_mongo_files(self.access_code)
        diversity = Path(files['diversity_output'])
        summary = {}
        summary_files = defaultdict(list)

        # Convert and store the otu table
        cmd = '{} biom convert -i {} -o {} --to-tsv --header-key="taxonomy"'
        run(cmd.format(self.jobtext[0],
                       Path(files['otu_output']) / 'otu_table.biom',
                       self.path / 'otu_table.tsv'),
            shell=True, check=True)

        with open(self.path / 'otu_table.tsv') as f:
            summary[Path(f.name).name] = f.read()
        summary_files['otu'].append('otu_table.tsv')

        def collect_files(path, catagory):
            """ Collect the contents of all files match the regex in path """
            files = glob(str(diversity / path.format(depth=self.sampling_depth)))
            for data in files:
                with open(data) as f:
                    summary[Path(f.name).name] = f.read()
                summary_files[catagory].append(Path(data).name)

        collect_files('biom_table_summary.txt', 'otu')                       # Biom summary
        collect_files('arare_max{depth}/alpha_div_collated/*.txt', 'alpha')  # Alpha div
        collect_files('bdiv_even{depth}/*.txt', 'beta')                      # Beta div
        collect_files('taxa_plots/*.txt', 'taxa')                            # Taxa summary

        os.mkdir(Path(self.path) / 'summary')
        self.add_path('summary', '')
        # Put all the files in one location
        for key in summary.keys():
            with open(Path(self.path) / 'summary/{}'.format(key), 'w') as f:
                f.write(summary[key])

        cmd = 'zip -r {} {}'.format(self.path / 'summary.zip', self.path / 'summary')
        run(cmd, shell=True, check=True)

        cmd = 'cp {} {}'.format(files['mapping'], self.path / 'summary/.')
        run(cmd, shell=True, check=True)

        summarize_qiime1(files=summary_files, execute=True, name='analysis', run_path=self.path / 'summary')
        log('Summary completed successfully')
        return self.path / 'summary/analysis.pdf'

    def run_analysis(self):
        """ Perform some analysis. """
        self.create_qiime_mapping_file()
        self.validate_mapping()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
        jobfile = self.path / (self.run_id + '_job')
        self.add_path(jobfile, '.lsf')
        error_log = self.path / self.run_id
        self.add_path(error_log, '.err')
        if self.testing:
            self.jobtext = ['#!/usr/bin/bash'] + self.jobtext
            # Open the jobfile to write all the commands
            with open(str(jobfile) + '.lsf', 'w') as f:
                f.write('\n'.join(self.jobtext))
            # Run the command
            run('sh {}.lsf &> {}.err'.format(jobfile, error_log), shell=True, check=True)
        else:
            # Get the job header text from the template
            with open(JOB_TEMPLATE) as f1:
                temp = f1.read()
            # Open the jobfile to write all the commands
            with open(str(jobfile) + '.lsf', 'w') as f:
                # Add the appropriate values
                params = self.get_job_params()
                f.write(temp.format(**params))
                f.write('\n'.join(self.jobtext))
            # Submit the job
            output = run('bsub < {}.lsf'.format(jobfile), stdout=PIPE, shell=True, check=True)
            job_id = int(str(output.stdout).split(' ')[1].strip('<>'))
            self.wait_on_job(job_id)

    def run(self):
        """ Execute all the necessary actions. """
        if self.analysis:
            self.run_analysis()
        self.sanity_check()
        summary = self.summarize()
        self.move_user_files()
        doc = self.db.get_metadata(self.access_code)
        send_email(doc.email,
                   doc.owner,
                   'analysis',
                   analysis_type='Qiime1',
                   study_name=doc.study,
                   testing=self.testing,
                   summary=summary)


class Qiime2(Tool):
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, testing):
        super().__init__(owner, access_code, atype, testing)
        if testing:
            self.jobtext.append('source activate qiime2;')
        else:
            self.jobtext.append('module load qiime2/2018.4;')

    # ======================= #
    # # # Qiime2 Commands # # #
    # ======================= #
    def qimport(self, itype='EMPSingleEndSequences'):
        """ Split the libraries and perform quality analysis. """
        files, path = self.db.get_mongo_files(self.access_code)

        # Add the split directory to the MetaData object
        self.db.update_metadata(self.access_code,
                                'working_file',
                                'qiime_artifact.qza')
        os.mkdir(Path(self.path) / 'import_dir')
        self.db.update_metadata(self.access_code,
                                'working_dir',
                                Path(self.path) / 'import_dir')
        files, path = self.db.get_mongo_files(self.access_code)
        run('ln -s {} {}'.format(Path(self.path) / 'barcodes.fastq.gz',
                                 Path(files['working_dir']) / 'barcodes.fastq.gz'),
            shell=True, check=True)
        run('ln -s {} {}'.format(Path(self.path) / 'sequences.fastq.gz',
                                 Path(files['working_dir']) / 'sequences.fastq.gz'),
            shell=True, check=True)

        # Run the script
        cmd = 'qiime tools import --type {} --input-path {} --output-path {};'
        command = cmd.format(itype, files['working_dir'], files['working_file'])
        self.jobtext.append(command)

    def demultiplex(self):
        """ Demultiplex the reads. """
        # Add the otu directory to the MetaData object
        self.add_path('demux_file', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = [
            'qiime demux emp-single',
            '--i-seqs {}'.format(files['working_file']),
            '--m-barcodes-file {}'.format(files['mapping']),
            '--m-barcodes-column {}'.format('BarcodeSequence'),
            '--o-per-sample-sequences {};'.format(files['demux_file'])
        ]
        self.jobtext.append(' '.join(cmd))

    def demux_visualize(self):
        """ Create visualization summary for the demux file. """
        self.add_path('demux_viz', '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = [
            'qiime demux summarize',
            '--i-data {}'.format(files['demux_file']),
            '--o-visualization {};'.format(files['demux_viz'])
        ]
        self.jobtext.append(' '.join(cmd))

    def tabulate(self):
        """ Run tabulate visualization. """
        self.add_path('stats_{}_visual'.format(self.atype), '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime metadata tabulate',
            '--m-input-file {}'.format(files['stats_{}'.format(self.atype)]),
            '--o-visualization {};'.format(files['stats_{}_visual'.format(self.atype)])
        ]
        self.jobtext.append(' '.join(cmd))

    def dada2(self, p_trim_left=0, p_trunc_len=120):
        """ Run DADA2 analysis on the demultiplexed file. """
        # Index new files
        self.add_path('rep_seqs_dada2', '.qza')
        self.add_path('table_dada2', '.qza')
        self.add_path('stats_dada2', '.qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime dada2 denoise-single',
            '--i-demultiplexed-seqs {}'.format(files['demux_file']),
            '--p-trim-left {}'.format(p_trim_left),
            '--p-trunc-len {}'.format(p_trunc_len),
            '--o-representative-sequences {}'.format(files['rep_seqs_dada2']),
            '--o-table {}'.format(files['table_dada2']),
            '--o-denoising-stats {}'.format(files['stats_dada2']),
            '--p-n-threads {};'.format(self.num_jobs)
        ]
        self.jobtext.append(' '.join(cmd))

    def dada2_visualize(self):
        """ Visualize the dada2 results. """

    def deblur_filter(self):
        """ Run Deblur analysis on the demultiplexed file. """
        self.add_path('demux_filtered', '.qza')
        self.add_path('demux_filter_stats', '.qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime quality-filter q-score',
            '--i-demux {}'.format(files['demux_file']),
            '--o-filtered-sequences {}'.format(files['demux_filtered']),
            '--o-filter-stats {};'.format(files['demux_filter_stats'])
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_denoise(self, p_trim_length=120):
        """ Run Deblur analysis on the demultiplexed file. """
        self.add_path('rep_seqs_deblur', '.qza')
        self.add_path('table_deblur', '.qza')
        self.add_path('stats_deblur', '.qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime deblur denoise-16S',
            '--i-demultiplexed-seqs {}'.format(files['demux_filtered']),
            '--p-trim-length {}'.format(p_trim_length),
            '--o-representative-sequences {}'.format(files['rep_seqs_deblur']),
            '--o-table {}'.format(files['table_deblur']),
            '--p-sample-stats',
            '--p-jobs-to-start {}'.format(self.num_jobs),
            '--o-stats {};'.format(files['stats_deblur'])
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_visualize(self):
        """ Create visualizations from deblur analysis. """
        self.add_path('stats_deblur_visual', '.qzv')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime deblur visualize-stats',
            '--i-deblur-stats {}'.format(files['stats_deblur']),
            '--o-visualization {};'.format(files['stats_deblur_visual'])
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mafft(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 1"""
        self.add_path('alignment', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime alignment mafft',
            '--i-sequences {}'.format(files['rep_seqs_{}'.format(self.atype)]),
            '--o-alignment {};'.format(files['alignment'])
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mask(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 2"""
        self.add_path('masked_alignment', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime alignment mask',
            '--i-alignment {}'.format(files['alignment']),
            '--o-masked-alignment {};'.format(files['masked_alignment'])
        ]
        self.jobtext.append(' '.join(cmd))

    def phylogeny_fasttree(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 3"""
        self.add_path('unrooted_tree', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime phylogeny fasttree',
            '--i-alignment {}'.format(files['masked_alignment']),
            '--o-tree {};'.format(files['unrooted_tree'])
        ]
        self.jobtext.append(' '.join(cmd))

    def phylogeny_midpoint_root(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 4"""
        self.add_path('rooted_tree', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime phylogeny midpoint-root',
            '--i-tree {}'.format(files['unrooted_tree']),
            '--o-rooted-tree {};'.format(files['rooted_tree'])
        ]
        self.jobtext.append(' '.join(cmd))

    def core_diversity(self, p_sampling_depth=1109):
        """ Run core diversity """
        self.add_path('core_metrics_results', '')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime diversity core-metrics-phylogenetic',
            '--i-phylogeny {}'.format(files['rooted_tree']),
            '--i-table {}'.format(files['table_{}'.format(self.atype)]),
            '--p-sampling-depth {}'.format(p_sampling_depth),
            '--m-metadata-file {}'.format(files['mapping']),
            '--p-n-jobs {} '.format(self.num_jobs),
            '--output-dir {};'.format(files['core_metrics_results'])
        ]
        self.jobtext.append(' '.join(cmd))

    def alpha_diversity(self, metric='faith_pd'):
        """
        Run core diversity.
        metric : ('faith_pd' or 'evenness')
        """
        self.add_path('{}_group_significance'.format(metric), '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime diversity alpha-group-significance',
            '--i-alpha-diversity {}'.format(Path(files['core_metrics_results']) / '{}_vector.qza'.format(metric)),
            '--m-metadata-file {}'.format(files['mapping']),
            '--o-visualization {}&'.format(files['{}_group_significance'.format(metric)])
        ]
        self.jobtext.append(' '.join(cmd))

    def beta_diversity(self, column='Nationality'):
        """
        Run core diversity.
        column: Some column from the metadata file
        """
        self.add_path('unweighted_{}_significance'.format(column), '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime diversity beta-group-significance',
            '--i-distance-matrix {}'.format(Path(files['core_metrics_results']) / 'unweighted_unifrac_distance_matrix.qza'),
            '--m-metadata-file {}'.format(files['mapping']),
            '--m-metadata-column {}'.format(column),
            '--o-visualization {}'.format(files['unweighted_{}_significance'.format(column)]),
            '--p-pairwise&'
        ]
        self.jobtext.append(' '.join(cmd))

    def alpha_rarefaction(self, max_depth=4000):
        """
        Create plots for alpha rarefaction.
        """
        self.add_path('alpha_rarefaction', '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime diversity alpha-rarefaction',
            '--i-table {}'.format(files['table_{}'.format(self.atype)]),
            '--i-phylogeny {}'.format(files['rooted_tree']),
            '--p-max-depth {}'.format(max_depth),
            '--m-metadata-file {}'.format(files['mapping']),
            '--o-visualization {}&'.format(files['alpha_rarefaction'])
        ]
        self.jobtext.append(' '.join(cmd))

    def classify_taxa(self, classifier):
        """
        Create plots for alpha rarefaction.
        """
        self.add_path('taxonomy', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime feature-classifier classify-sklearn'
            '--i-classifier {}'.format(classifier),
            '--i-reads {}'.format(files['rep_seq_{}'.format(self.atype)]),
            '--o-classification {}&'.format(files['taxonomy'])
        ]
        self.jobtext.append(' '.join(cmd))

    def sanity_check(self):
        """ Check that the counts after split_libraries and final counts match """
        files, path = self.db.get_mongo_files(self.access_code)
        # Check the counts at the beginning of the analysis
        cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                files['demux_file'],
                                                                files['demux_export'])
        run(cmd, shell=True, check=True)

        df = read_csv(Path(files['demux_export']) / 'per-sample-fastq-counts.csv', sep=',', header=0)
        initial_count = sum(df['Sequence count'])
        # Check the counts after DADA2/DeBlur
        cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                files['table_{}'.format(self.atype)],
                                                                files['stats_export'])
        run(cmd, shell=True, check=True)

        cmd = '{} biom summarize-table -i {}'.format(self.jobtext[0], Path(files['stats_export']) / 'feature-table.biom')
        result = run(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        final_count = int(result.stdout.decode('utf-8').split('\n')[2].split(':')[1].strip().replace(',', ''))
        if abs(initial_count - final_count) > 0.05 * (initial_count + final_count):
            message = 'Large difference ({}) between initial and final counts'
            raise AnalysisError(message.format(initial_count - final_count))

    def setup_analysis(self):
        """ Create the job file for the analysis. """
        self.create_qiime_mapping_file()
        self.qimport()
        self.demultiplex()
        self.demux_visualize()
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
        # Run these commands in parallel
        self.alpha_diversity()
        for col in self.columns:
            self.beta_diversity(col)
        self.alpha_rarefaction()
        self.classify_taxa(STORAGE_DIR / 'classifier.qza')
        # Wait for them all to finish
        self.jobtext.append('wait')

    def analysis(self):
        """ Perform some analysis. """
        self.setup_analysis()
        try:
            jobfile = self.path / (self.run_id + '_job')
            self.add_path(jobfile, 'lsf')
            error_log = self.path / self.run_id
            self.add_path(error_log, 'err')
            if self.testing:
                self.jobtext = ['#!/usr/bin/bash'] + self.jobtext
                # Open the jobfile to write all the commands
                with open(str(jobfile) + '.lsf', 'w') as f:
                    f.write('\n'.join(self.jobtext))
                # Run the command
                run('sh {}.lsf &> {}.err'.format(jobfile, error_log), shell=True, check=True)
            else:
                # Get the job header text from the template
                with open(JOB_TEMPLATE) as f1:
                    temp = f1.read()
                # Open the jobfile to write all the commands
                with open(str(jobfile) + '.lsf', 'w') as f:
                    options = self.get_job_params()
                    # Add the appropriate values
                    f.write(temp.format(**options))
                    f.write('\n'.join(self.jobtext))
                # Submit the job
                output = run('bsub < {}.lsf'.format(jobfile), stdout=PIPE, shell=True, check=True)
                job_id = int(output.stdout.decode('utf-8').split(' ')[1].strip('<>'))
                self.wait_on_job(job_id)

            self.sanity_check()
            doc = self.db.get_metadata(self.access_code)
            self.move_user_files()
            send_email(doc.email, doc.owner, 'analysis', analysis_type='Qiime2 (2018.4) ' + self.atype, study_name=doc.study)
        except CalledProcessError as e:
            raise AnalysisError(e.args[0])

    def summarize(self):
        """ Create summary of the files produced by the qiime2 analysis. """
        files, path = self.db.get_mongo_files(self.access_code)
        files['alpha_rarefaction'] = '/home/david/Work/mmeds-meta/server/data/david_0/q2-dada/'
        files['core_metrics_results'] = '/home/david/Work/mmeds-meta/server/data/david_0/q2-dada/core_metrics_results_cqyob'

        summary = {}
        # Get Alpha rarefaction
        # Get Taxa
        cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                files['alpha_rarefaction'],
                                                                self.path / 'temp')
        run(cmd, shell=True, check=True)
        with open(self.path / 'temp/observed_otus.csv') as f:
            summary[Path(f.name).name] = f.read()
        rmtree(self.path / 'temp')

        # Get Beta
        for pref in ['', 'un']:
            beta_file = Path(files['core_metrics_results']) / '{}weighted_unifrac_distance_matrix.qza'.format(pref)

            cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                    beta_file,
                                                                    self.path / 'temp')
            run(cmd, shell=True, check=True)
            with open(self.path / 'temp/distance-matrix.tsv') as f:
                summary['beta-' + str(Path(f.name).name)] = f.read()
            rmtree(self.path / 'temp')

        # Get Beta
        for metric in ['shannon', 'evenness', 'faith_pd']:
            alpha_file = Path(files['core_metrics_results']) / '{}_vector.qza'.format(metric)

            cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                    alpha_file,
                                                                    self.path / 'temp')
            run(cmd, shell=True, check=True)
            with open(self.path / 'temp/alpha-diversity.tsv') as f:
                summary['{}-'.format(metric) + str(Path(f.name).name)] = f.read()
            rmtree(self.path / 'temp')

        for key in summary.keys():
            print(key)
            with open(Path(self.path) / 'summary/{}'.format(key), 'w') as f:
                f.write(summary[key])

        cmd = 'zip -r {} {}'.format(self.path / 'summary.zip', self.path / 'summary')
        run(cmd, shell=True, check=True)

        self.summary_analysis(summary)


def run_analysis(qiime):
    """ Run qiime analysis. """
    try:
        qiime.run()
    except (AnalysisError, CalledProcessError) as e:
        email = get_email(qiime.owner, testing=qiime.testing)
        send_email(email,
                   qiime.owner,
                   'error',
                   analysis_type=qiime.atype,
                   error=e.message,
                   testing=qiime.testing)


def test(time, atype):
    """ Simple function for analysis called during testing """
    sleep(time)


def spawn_analysis(atype, user, access_code, testing):
    """ Start running the analysis in a new process """
    if 'qiime1' in atype:
        qiime = Qiime1(user, access_code, atype, testing)
        p = mp.Process(target=run_analysis, args=(qiime,))
    elif 'qiime2' in atype:
        qiime = Qiime2(user, access_code, atype, testing)
        p = mp.Process(target=run_analysis, args=(qiime,))
    elif 'test' in atype:
        time = float(atype.split('-')[-1])
        p = mp.Process(target=test, args=(time, atype))
    p.start()
    return p
