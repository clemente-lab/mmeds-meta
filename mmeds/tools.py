from pandas import read_csv
from pathlib import Path
from subprocess import run, CalledProcessError, PIPE
from shutil import copyfile
from time import sleep
import os
import multiprocessing as mp

from mmeds.database import Database
from mmeds.config import get_salt, JOB_TEMPLATE
from mmeds.mmeds import send_email
from mmeds.authentication import get_email
from mmeds.error import AnalysisError


class Qiime1Analysis:
    """ A class for qiime 1.9.1 analysis of uploaded studies. """

    def __init__(self, owner, access_code, testing):
        self.db = Database('', owner=owner, testing=testing)
        self.access_code = access_code
        files, path = self.db.get_mongo_files(self.access_code)
        self.testing = testing
        self.jobtext = []
        self.owner = owner
        self.num_jobs = 10
        if testing:
            self.jobtext.append('source activate qiime1;')
        else:
            self.jobtext.append('module load qiime/1.9.1;')
        self.path = None
        self.path = self.setup_dir(path)

    def __del__(self):
        del self.db

    def setup_dir(self, path):
        """ Setup the directory to run the analysis. """
        count = 0
        new_dir = Path(path) / 'analysis{}'.format(count)
        while os.path.exists(new_dir):
            count += 1
            new_dir = Path(path) / 'analysis{}'.format(count)

        # Add the split directory to the MetaData object
        add_path(self, 'analysis{}'.format(count), '')

        files, path = self.db.get_mongo_files(self.access_code)

        run('mkdir {}'.format(new_dir), shell=True, check=True)

        # Create links to the files
        run('ln {} {}'.format(files['barcodes'],
                              new_dir / 'barcodes.fastq.gz'),
            shell=True, check=True)
        run('ln {} {}'.format(files['reads'],
                              new_dir / 'sequences.fastq.gz'),
            shell=True, check=True)
        return new_dir

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(files['mapping'], self.path)
        self.jobtext.append(cmd)

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        metadata = self.db.get_metadata(self.access_code)
        fp = metadata.files['metadata']
        mdata = read_csv(fp, header=1, sep='\t')

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'

        headers = list(mdata.columns)

        si = headers.index('SpecimenID')
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
                        row.append(str(mdata['SpecimenID'][row_index]))
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
        cmd = 'split_libraries_fastq.py -o {} -i {} -b {} -m {};'
        command = cmd.format(files['split_output'], files['reads'], files['barcodes'], files['mapping'])
        self.jobtext.append(command)

    def pick_otu(self, reference='closed'):
        """ Run the pick OTU scripts. """
        add_path(self, 'otu_output', '')
        files, path = self.db.get_mongo_files(self.access_code)

        with open(Path(path) / 'params.txt', 'w') as f:
            f.write('pick_otus:enable_rev_strand_match True\n')

        # Run the script
        cmd = 'pick_{}_reference_otus.py -a -O {} -o {} -i {} -p {};'
        command = cmd.format(reference,
                             self.num_jobs,
                             files['otu_output'],
                             Path(files['split_output']) / 'seqs.fna',
                             Path(path) / 'params.txt')
        self.jobtext.append(command)

    def core_diversity(self):
        """ Run the core diversity analysis script. """
        add_path(self, 'diversity_output', '')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = 'core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {};'
        command = cmd.format(files['diversity_output'],
                             Path(files['otu_output']) / 'otu_table_mc2_w_tax_no_pynast_failures.biom',
                             files['mapping'],
                             Path(files['otu_output']) / 'rep_set.tre',
                             1114)
        self.jobtext.append(command)

    def analysis(self):
        """ Perform some analysis. """
        self.setup_dir()
        self.create_qiime_mapping_file()
        self.validate_mapping()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
        run_id = get_salt(5)
        jobfile = self.path / (run_id + '_job')
        add_path(self, jobfile, 'lsf')
        error_log = self.path / run_id
        add_path(self, error_log, 'err')
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
                params = get_job_params(self.owner, self.path, run_id)
                f.write(temp.format(**params))
                f.write('\n'.join(self.jobtext))
            # Submit the job
            output = run('bsub < {}.lsf'.format(jobfile), stdout=PIPE, shell=True, check=True)
            job_id = int(str(output.stdout).split(' ')[1].strip('<>'))

        wait_on_job(job_id)

        move_user_files(self)
        doc = self.db.get_metadata(self.access_code)
        send_email(doc.email,
                   doc.owner,
                   'analysis',
                   analysis_type='Qiime1',
                   study_name=doc.study,
                   testing=self.testing)


class Qiime2Analysis:
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, testing):
        self.db = Database('', owner=owner, testing=testing)
        self.access_code = access_code
        self.atype = atype.split('-')[-1]
        self.overwrite = False
        self.jobtext = []
        self.testing = testing
        self.owner = owner
        if testing:
            self.jobtext.append('source activate qiime2;')
        else:
            self.jobtext.append('module load qiime2/2018.4;')
        files, path = self.db.get_mongo_files(self.access_code)
        self.path = None
        self.path = self.setup_dir(path)

    def __del__(self):
        del self.db

    def setup_dir(self, path):
        """ Setup the directory to run the analysis. """
        count = 0
        new_dir = Path(path) / 'analysis{}'.format(count)
        while os.path.exists(Path(path) / new_dir):
            count += 1
            new_dir = 'analysis{}'.format(count)

        # Add the split directory to the MetaData object
        add_path(self, new_dir, '')

        files, path = self.db.get_mongo_files(self.access_code)

        run('mkdir {}'.format(new_dir), shell=True, check=True)

        # Create links to the files
        run('ln {} {}'.format(files['barcodes'],
                              Path(new_dir) / 'barcodes.fastq.gz'),
            shell=True, check=True)
        run('ln {} {}'.format(files['reads'],
                              Path(new_dir) / 'sequences.fastq.gz'),
            shell=True, check=True)
        return new_dir

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(files['mapping'], self.path)
        self.jobtext.append(cmd)

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        metadata = self.db.get_metadata(self.access_code)
        fp = metadata.files['metadata']
        mdata = read_csv(fp, header=1, sep='\t')

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'

        headers = list(mdata.columns)

        si = headers.index('SpecimenID')
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
                        row.append(str(mdata['SpecimenID'][row_index]))
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
                                'qiime_artifact.qza')
        files, path = self.db.get_mongo_files(self.access_code)

        # Run the script
        cmd = 'qiime tools import --type {} --input-path {} --output-path {};'
        command = cmd.format(itype, self.path, files['working_file'])
        self.jobtext.append(command)

    def demultiplex(self):
        """ Run the core diversity analysis script. """
        # Add the otu directory to the MetaData object
        add_path(self, 'demux_file', '.qza')
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
        add_path(self, 'stats_{}_visual'.format(self.atype), '.qzv')
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
        add_path(self, 'rep_seqs_dada2', '.qza')
        add_path(self, 'table_dada2', '.qza')
        add_path(self, 'stats_dada2', '.qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime dada2 denoise-single',
            '--i-demultiplexed-seqs {}'.format(files['demux_file']),
            '--p-trim-left {}'.format(p_trim_left),
            '--p-trunc-len {}'.format(p_trunc_len),
            '--o-representative-sequences {}'.format(files['rep_seqs_dada2']),
            '--o-table {}'.format(files['table_dada2']),
            '--o-denoising-stats {};'.format(files['stats_dada2'])
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_filter(self):
        """ Run Deblur analysis on the demultiplexed file. """
        add_path(self, 'demux_filtered', '.qza')
        add_path(self, 'demux_filter_stats', '.qza')

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
        add_path(self, 'rep_seqs_deblur', '.qza')
        add_path(self, 'table_deblur', '.qza')
        add_path(self, 'stats_deblur', '.qza')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime deblur denoise-16S',
            '--i-demultiplexed-seqs {}'.format(files['demux_filtered']),
            '--p-trim-length {}'.format(p_trim_length),
            '--o-representative-sequences {}'.format(files['rep_seqs_deblur']),
            '--o-table {}'.format(files['table_deblur']),
            '--p-sample-stats',
            '--o-stats {};'.format(files['stats_deblur'])
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_visualize(self):
        """ Create visualizations from deblur analysis. """
        add_path(self, 'stats_deblur_visual', '.qzv')

        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime deblur visualize-stats',
            '--i-deblur-stats {}'.format(files['stats_deblur']),
            '--o-visualization {};'.format(files['stats_deblur_visual'])
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mafft(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 1"""
        add_path(self, 'alignment', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime alignment mafft',
            '--i-sequences {}'.format(files['rep_seqs_{}'.format(self.atype)]),
            '--o-alignment {};'.format(files['alignment'])
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mask(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 2"""
        add_path(self, 'masked_alignment', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime alignment mask',
            '--i-alignment {}'.format(files['alignment']),
            '--o-masked-alignment {};'.format(files['masked_alignment'])
        ]
        self.jobtext.append(' '.join(cmd))

    def phylogeny_fasttree(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 3"""
        add_path(self, 'unrooted_tree', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime phylogeny fasttree',
            '--i-alignment {}'.format(files['masked_alignment']),
            '--o-tree {};'.format(files['unrooted_tree'])
        ]
        self.jobtext.append(' '.join(cmd))

    def phylogeny_midpoint_root(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 3"""
        add_path(self, 'rooted_tree', '.qza')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime phylogeny midpoint-root',
            '--i-tree {}'.format(files['unrooted_tree']),
            '--o-rooted-tree {};'.format(files['rooted_tree'])
        ]
        self.jobtext.append(' '.join(cmd))

    def core_diversity(self, p_sampling_depth=1109):
        """ Run core diversity """
        add_path(self, 'core_metrics_results', '')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime diversity core-metrics-phylogenetic',
            '--i-phylogeny {}'.format(files['rooted_tree']),
            '--i-table {}'.format(files['table_{}'.format(self.atype)]),
            '--p-sampling-depth {}'.format(p_sampling_depth),
            '--m-metadata-file {}'.format(files['mapping']),
            '--output-dir {};'.format(files['core_metrics_results'])
        ]
        self.jobtext.append(' '.join(cmd))

    def alpha_diversity(self, metric='faith_pd'):
        """
        Run core diversity.
        metric : ('faith_pd' or 'evenness')
        """
        add_path(self, '{}_group_significance'.format(metric), '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime diversity alpha-group-significance',
            '--i-alpha-diversity {}'.format(Path(files['core_metrics_results']) / '{}_vector.qza'.format(metric)),
            '--m-metadata-file {}'.format(files['mapping']),
            '--o-visualization {};'.format(files['{}_group_significance'.format(metric)])
        ]
        self.jobtext.append(' '.join(cmd))

    def beta_diversity(self, column='Nationality'):
        """
        Run core diversity.
        column: Some column from the metadata file
        """
        add_path(self, 'unweighted_{}_significance'.format(column), '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime diversity beta-group-significance',
            '--i-distance-matrix {}'.format(Path(files['core_metrics_results']) / 'unweighted_unifrac_distance_matrix.qza'),
            '--m-metadata-file {}'.format(files['mapping']),
            '--m-metadata-column {}'.format(column),
            '--o-visualization {}'.format(files['unweighted_{}_significance'.format(column)]),
            '--p-pairwise;'
        ]
        self.jobtext.append(' '.join(cmd))

    def alpha_rarefaction(self, max_depth=4000):
        """
        Create plots for alpha rarefaction.
        """
        add_path(self, 'alpha_rarefaction', '.qzv')
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = [
            'qiime diversity alpha-rarefaction',
            '--i-table {}'.format(files['table_{}'.format(self.atype)]),
            '--i-phylogeny {}'.format(files['rooted_tree']),
            '--p-max-depth {}'.format(max_depth),
            '--m-metadata-file {}'.format(files['mapping']),
            '--o-visualization {};'.format(files['alpha_rarefaction'])
        ]
        self.jobtext.append(' '.join(cmd))

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
        run_id = get_salt(5)
        jobfile = self.path / (run_id + '_job')
        add_path(self, jobfile, 'lsf')
        error_log = self.path / (run_id)
        add_path(self, error_log, 'err')
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
                options = get_job_params(self.owner, self.path, run_id)
                # Add the appropriate values
                f.write(temp.format(**options))
                f.write('\n'.join(self.jobtext))
            # Submit the job
            output = run('bsub < {}.lsf'.format(jobfile), stdout=PIPE, shell=True, check=True)
            job_id = int(output.stdout.decode('utf-8').split(' ')[1].strip('<>'))

        wait_on_job(job_id)
        doc = self.db.get_metadata(self.access_code)
        move_user_files(self)
        send_email(doc.email, doc.owner, 'analysis', analysis_type='Qiime2 (2018.4) ' + self.atype, study_name=doc.study)


def get_job_params(owner, path, run_id):
    params = {
        'walltime': '48:00',
        'jobname': owner + '_' + run_id,
        'nodes': 10,
        'memory': 1000,
        'jobid': path / run_id
    }
    return params


def wait_on_job(job_id):
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


def move_user_files(qiime):
    """ Move all files intended for the user to a set location. """
    try:
        add_path(qiime, 'visualizations_dir', '')
        files, path = qiime.db.get_mongo_files(qiime.access_code)
        os.mkdir(files['visualizations_dir'])
        for key in files.keys():
            f = Path(files[key])
            if '.qzv' in files[key]:
                new_file = f.name
                copyfile(files[key], Path(files['visualizations_dir']) / new_file)
    except FileNotFoundError as e:
        raise AnalysisError(e.args[0])


def add_path(qiime, name, extension):
    """ Add a file or directory to the document identified by qiime.access_code. """
    new_file = Path(qiime.path) / (str(name) + '_' + get_salt(5) + extension)
    while os.path.exists(new_file):
        new_file = Path(qiime.path) / (str(name) + '_' + get_salt(5) + extension)
    qiime.db.update_metadata(qiime.access_code, str(name), new_file)


def run_qiime1(user, access_code, testing):
    """ Run qiime analysis. """
    try:
        qa = Qiime1Analysis(user, access_code, testing)
        qa.analysis()
    except (AnalysisError, CalledProcessError) as e:
        email = get_email(user, testing=testing)
        send_email(email, user, 'error', analysis_type='Qiime1.9.1', error=e.message, testing=testing)
    with Database('', owner=user, testing=testing) as db:
        files = db.check_files(access_code)
        print(files)


def run_qiime2(user, access_code, atype, testing):
    """ Run qiime analysis. """
    try:
        qa = Qiime2Analysis(user, access_code, atype, testing)
        qa.analysis()
    except (AnalysisError, CalledProcessError) as e:
        email = get_email(user, testing=testing)
        send_email(email, user, 'error', analysis_type='Qiime2 (2018.4)', error=e.message, testing=testing)
    with Database('', owner=user, testing=testing) as db:
        files = db.check_files(access_code)
        print(files)


def test(time, atype):
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
