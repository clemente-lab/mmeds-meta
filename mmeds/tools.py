from pathlib import Path
from subprocess import run, CalledProcessError, PIPE
from shutil import copyfile
from time import sleep
from pandas import read_csv

import os
import multiprocessing as mp

from mmeds.database import Database
from mmeds.config import get_salt, JOB_TEMPLATE
from mmeds.mmeds import send_email
from mmeds.authentication import get_email
from mmeds.error import AnalysisError


class Tool:
    """ The base class for tools used by mmeds """

    def __init__(self, owner, access_code, atype, testing, threads=10):
        self.db = Database('', owner=owner, testing=testing)
        self.access_code = access_code
        files, path = self.db.get_mongo_files(self.access_code)
        self.testing = testing
        self.jobtext = []
        self.owner = owner
        self.num_jobs = threads
        self.atype = atype.split('-')[1]
        self.path, self.run_id = self.setup_dir(path)

        # Add the split directory to the MetaData object
        self.add_path('analysis{}'.format(self.run_id), '')

    def __del__(self):
        del self.db

    def setup_dir(self, path):
        """ Setup the directory to run the analysis. """
        run_id = 0
        new_dir = Path(path) / 'analysis{}'.format(run_id)
        while os.path.exists(new_dir):
            run_id += 1
            new_dir = Path(path) / 'analysis{}'.format(run_id)

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
            'nodes': 10,
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
                                 1114)
        else:
            command = cmd.format(files['diversity_output'],
                                 Path(files['otu_output']) / 'otu_table.biom',
                                 files['mapping'],
                                 Path(files['otu_output']) / '97_otus.tree',
                                 1114)

        self.jobtext.append(command)

    def sanity_check(self):
        """ Check that counts match after split_libraries and pick_otu. """
        files, path = self.db.get_mongo_files(self.access_code)

        cmd = '{} count_seqs.py -i {}'.format(self.jobtext[0],
                                              Path(files['split_output']) / 'seqs.fna')
        output = run(cmd, shell=True, stdin=PIPE, stderr=PIPE, stdout=PIPE)
        initial_count = int(output.stdout.decode('utf-8').split('\n')[1].split(' ')[0])

        with open(Path(files['diversity_output']) / 'biom_table_summary.txt') as f:
            final_count = int(f.readlines()[2].split(':')[-1].strip().replace(',', ''))
        if abs(initial_count - final_count) > 0.05 * (initial_count + final_count):
            message = 'Large difference ({}) between initial and final counts'
            raise AnalysisError(message.format(initial_count - final_count))

    def analysis(self):
        """ Perform some analysis. """
        self.create_qiime_mapping_file()
        self.validate_mapping()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
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
            run('sh {}.lsf > {}.err'.format(jobfile, error_log), shell=True, check=True)
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
        self.sanity_check()
        self.move_user_files()
        doc = self.db.get_metadata(self.access_code)
        send_email(doc.email,
                   doc.owner,
                   'analysis',
                   analysis_type='Qiime1',
                   study_name=doc.study,
                   testing=self.testing)


class Qiime2(Tool):
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, testing):
        super().__init__(owner, access_code, atype, testing)
        if testing:
            self.jobtext.append('source activate qiime2;')
        else:
            self.jobtext.append('module load qiime2/2018.4;')

    def qimport(self, itype='EMPSingleEndSequences'):
        """ Split the libraries and perform quality analysis. """
        files, path = self.db.get_mongo_files(self.access_code)

        # Add the split directory to the MetaData object
        self.db.update_metadata(self.access_code,
                                'working_file',
                                'qiime_artifact.qza')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = 'qiime tools import --type {} --input-path {} --output-path {};'
        command = cmd.format(itype, self.path, files['working_file'])
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
        """ Generate a tree for phylogenetic diversity analysis. Step 3"""
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

    def sanity_check(self):
        """ Check that the counts after split_libraries and final counts match """

    def analysis(self):
        """ Perform some analysis. """
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
        # Run these commands in parallel
        self.alpha_diversity()
        self.beta_diversity()
        self.alpha_rarefaction()
        # Wait for them all to finish
        self.jobtext.append('wait')

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
            run('sh {}.lsf > {}.err'.format(jobfile, error_log), shell=True, check=True)
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
        doc = self.db.get_metadata(self.access_code)
        self.move_user_files()
        send_email(doc.email, doc.owner, 'analysis', analysis_type='Qiime2 (2018.4) ' + self.atype, study_name=doc.study)


def run_qiime1(user, access_code, atype, testing):
    """ Run qiime analysis. """
    try:
        qa = Qiime1(user, access_code, atype, testing)
        qa.analysis()
    except (AnalysisError, CalledProcessError) as e:
        email = get_email(user, testing=testing)
        send_email(email, user, 'error', analysis_type='Qiime1.9.1', error=e.message, testing=testing)


def run_qiime2(user, access_code, atype, testing):
    """ Run qiime analysis. """
    try:
        qa = Qiime2(user, access_code, atype, testing)
        qa.analysis()
    except (AnalysisError, CalledProcessError) as e:
        email = get_email(user, testing=testing)
        send_email(email, user, 'error', analysis_type='Qiime2 (2018.4)', error=e.message, testing=testing)


def test(time, atype):
    """ Simple function for analysis called during testing """
    sleep(time)


def analysis_runner(atype, user, access_code, testing):
    """ Start running the analysis in a new process """
    if 'qiime1' in atype:
        p = mp.Process(target=run_qiime1, args=(user, access_code, testing))
    elif 'qiime2' in atype:
        p = mp.Process(target=run_qiime2, args=(user, access_code, atype, testing))
    elif 'test' in atype:
        time = float(atype.split('-')[-1])
        p = mp.Process(target=test, args=(time, atype))
    p.start()
    return p
