from subprocess import run, CalledProcessError
from shutil import rmtree
from pandas import read_csv
from multiprocessing import Process

from mmeds.database import Database
from mmeds.config import JOB_TEMPLATE, STORAGE_DIR, DATABASE_DIR
from mmeds.util import send_email, log, setup_environment, load_metadata
from mmeds.error import AnalysisError
from mmeds.tool import Tool
from mmeds.spawn import run_analysis


class Qiime2(Tool):
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing):
        super().__init__(owner, access_code, atype, config, testing)
        load = 'module use {}/.modules/modulefiles; module load qiime2/2019.1;'
        self.jobtext.append(load.format(DATABASE_DIR.parent))
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))

    # =============== #
    # Qiime2 Commands #
    # =============== #
    def qimport(self):
        """ Split the libraries and perform quality analysis. """

        self.files['demux_file'] = self.path / 'qiime_artifact.qza'

        if 'demuxed' in self.data_type:
            # If the reads are already demultiplexed import the whole directory
            cmd = [
                'qiime tools import ',
                '--type {} '.format('"SampleData[PairedEndSequencesWithQuality]"'),
                '--input-path {}'.format(self.get_file('for_reads')),
                '--input-format {}'.format('CasavaOneEightSingleLanePerSampleDirFmt'),
                '--output-path {};'.format(self.get_file('demux_file'))
            ]
            command = ' '.join(cmd)
        elif self.data_type == 'single_end':
            # Create a directory to import as a Qiime2 object
            self.files['working_file'] = self.path / 'qiime_artifact.qza'
            self.files['working_dir'] = self.path / 'import_dir'

            if not self.files['working_dir'].is_dir():
                self.files['working_dir'].mkdir()

            # Create links to the data in the qiime2 import directory
            (self.files['working_dir'] / 'barcodes.fastq.gz').symlink_to(self.files['barcodes'])
            (self.files['working_dir'] / 'sequences.fastq.gz').symlink_to(self.files['for_reads'])

            # Run the script
            cmd = 'qiime tools import --type {} --input-path {} --output-path {};'
            command = cmd.format('EMPSingleEndSequences',
                                 self.get_file('working_dir'),
                                 self.get_file('working_file'))
        elif self.data_type == 'paired_end':
            # Create a directory to import as a Qiime2 object
            self.files['working_file'] = self.path / 'qiime_artifact.qza'
            self.files['working_dir'] = self.path / 'import_dir'

            if not self.files['working_dir'].is_dir():
                self.files['working_dir'].mkdir()

            # Create links to the data in the qiime2 import directory
            (self.files['working_dir'] / 'barcodes.fastq.gz').symlink_to(self.files['barcodes'])
            (self.files['working_dir'] / 'forward.fastq.gz').symlink_to(self.files['for_reads'])
            (self.files['working_dir'] / 'reverse.fastq.gz').symlink_to(self.files['rev_reads'])

            # Run the script
            cmd = 'qiime tools import --type {} --input-path {} --output-path {};'
            command = cmd.format('EMPPairedEndSequences',
                                 self.get_file('working_dir'),
                                 self.get_file('working_file'))
        self.jobtext.append(command)

    def demultiplex(self):
        """ Demultiplex the reads. """
        # Add the otu directory to the MetaData object
        self.add_path('demux_file', '.qza')

        # Run the script
        cmd = [
            # Either emp-single or emp-paired depending on the data_type
            'qiime demux emp-{}'.format(self.data_type.split('_')[0]),
            '--i-seqs {}'.format(self.get_file('working_file')),
            '--m-barcodes-file {}'.format(self.get_file('mapping')),
            '--m-barcodes-column {}'.format('BarcodeSequence'),
            '--o-per-sample-sequences {};'.format(self.get_file('demux_file'))
        ]
        # Reverse compliment the barcodes in the mapping file if using paired reads
        if 'paired' in self.data_type:
            cmd = cmd[:3] + ['--p-rev-comp-mapping-barcodes '] + cmd[3:]
        self.jobtext.append(' '.join(cmd))

    def filter_by_metadata(self, column=None, value=None):
        """
            Filter the dataset based on some metadata parameter.
            ====================================================
            :column: Column to filter on, if not None
            :value: Value to have in column, if not None
        """
        self.add_path('filtered_table', '.qza')
        cmd = [
            'qiime feature-table filter-samples',
            '--i-table {}'.format(self.get_file('table_{}'.format(self.atype))),
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--o-filtered-table {}'.format(self.get_file('filtered_table'))
        ]

        if column is not None and value is not None:
            cmd.append('--p-where "{column}={value}')
        self.jobtext.append(' '.join(cmd))

    def demux_visualize(self):
        """ Create visualization summary for the demux file. """
        self.add_path('demux_viz', '.qzv')

        # Run the script
        cmd = [
            'qiime demux summarize',
            '--i-data {}'.format(self.get_file('demux_file')),
            '--o-visualization {};'.format(self.get_file('demux_viz'))
        ]
        self.jobtext.append(' '.join(cmd))

    def tabulate(self):
        """ Run tabulate visualization. """
        self.add_path('stats_{}_visual'.format(self.atype), '.qzv')
        cmd = [
            'qiime metadata tabulate',
            '--m-input-file {}'.format(self.get_file('stats_{}'.format(self.atype))),
            '--o-visualization {};'.format(self.get_file('stats_{}_visual'.format(self.atype)))
        ]
        self.jobtext.append(' '.join(cmd))

    def dada2(self, p_trim_left=0, p_trunc_len=0):
        """ Run DADA2 analysis on the demultiplexed file. """
        # Index new files
        self.add_path('rep_seqs_dada2', '.qza')
        self.add_path('table_dada2', '.qza')
        self.add_path('stats_dada2', '.qza')

        if 'single' in self.data_type:
            cmd = [
                'qiime dada2 denoise-single',
                '--i-demultiplexed-seqs {}'.format(self.get_file('demux_file')),
                '--p-trim-left {}'.format(p_trim_left),
                '--p-trunc-len {}'.format(p_trunc_len),
                '--o-representative-sequences {}'.format(self.get_file('rep_seqs_dada2')),
                '--o-table {}'.format(self.get_file('table_dada2')),
                '--o-denoising-stats {}'.format(self.get_file('stats_dada2')),
                '--p-n-threads {};'.format(self.num_jobs)
            ]
        elif 'paired' in self.data_type:
            cmd = [
                'qiime dada2 denoise-paired',
                '--i-demultiplexed-seqs {}'.format(self.get_file('demux_file')),
                '--p-trim-left-f {}'.format(p_trim_left),
                '--p-trim-left-r {}'.format(p_trim_left),
                '--p-trunc-len-f {}'.format(p_trunc_len),
                '--p-trunc-len-r {}'.format(p_trunc_len),
                '--o-representative-sequences {}'.format(self.get_file('rep_seqs_dada2')),
                '--o-table {}'.format(self.get_file('table_dada2')),
                '--o-denoising-stats {}'.format(self.get_file('stats_dada2')),
                '--p-n-threads {};'.format(self.num_jobs)
            ]
        self.jobtext.append(' '.join(cmd))

    def deblur_filter(self):
        """ Run Deblur analysis on the demultiplexed file. """
        self.add_path('demux_filtered', '.qza')
        self.add_path('demux_filter_stats', '.qza')
        cmd = [
            'qiime quality-filter q-score',
            '--i-demux {}'.format(self.get_file('demux_file')),
            '--o-filtered-sequences {}'.format(self.get_file('demux_filtered')),
            '--o-filter-stats {};'.format(self.get_file('demux_filter_stats')),
            '--quiet'
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_denoise(self, p_trim_length=120):
        """ Run Deblur analysis on the demultiplexed file. """
        self.add_path('rep_seqs_deblur', '.qza')
        self.add_path('table_deblur', '.qza')
        self.add_path('stats_deblur', '.qza')
        cmd = [
            'qiime deblur denoise-16S',
            '--i-demultiplexed-seqs {}'.format(self.get_file('demux_filtered')),
            '--p-trim-length {}'.format(p_trim_length),
            '--o-representative-sequences {}'.format(self.get_file('rep_seqs_deblur')),
            '--o-table {}'.format(self.get_file('table_deblur')),
            '--p-sample-stats',
            '--p-jobs-to-start {}'.format(self.num_jobs),
            '--o-stats {};'.format(self.get_file('stats_deblur')),
            '--quiet'
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_visualize(self):
        """ Create visualizations from deblur analysis. """
        self.add_path('stats_deblur_visual', '.qzv')
        cmd = [
            'qiime deblur visualize-stats',
            '--i-deblur-stats {}'.format(self.get_file('stats_deblur')),
            '--o-visualization {};'.format(self.get_file('stats_deblur_visual')),
            '--quiet'
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mafft(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 1"""
        self.add_path('alignment', '.qza')
        cmd = [
            'qiime alignment mafft',
            '--i-sequences {}'.format(self.get_file('rep_seqs_{}'.format(self.atype))),
            '--o-alignment {};'.format(self.get_file('alignment'))
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mask(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 2"""
        self.add_path('masked_alignment', '.qza')
        cmd = [
            'qiime alignment mask',
            '--i-alignment {}'.format(self.get_file('alignment')),
            '--o-masked-alignment {};'.format(self.get_file('masked_alignment'))
        ]
        self.jobtext.append(' '.join(cmd))

    def phylogeny_fasttree(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 3"""
        self.add_path('unrooted_tree', '.qza')
        cmd = [
            'qiime phylogeny fasttree',
            '--i-alignment {}'.format(self.get_file('masked_alignment')),
            '--o-tree {};'.format(self.get_file('unrooted_tree'))
        ]
        self.jobtext.append(' '.join(cmd))

    def phylogeny_midpoint_root(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 4"""
        self.add_path('rooted_tree', '.qza')
        cmd = [
            'qiime phylogeny midpoint-root',
            '--i-tree {}'.format(self.get_file('unrooted_tree')),
            '--o-rooted-tree {};'.format(self.get_file('rooted_tree'))
        ]
        self.jobtext.append(' '.join(cmd))

    def core_diversity(self):
        """ Run core diversity """
        self.add_path('core_metrics_results', '')
        cmd = [
            'qiime diversity core-metrics-phylogenetic',
            '--i-phylogeny {}'.format(self.get_file('rooted_tree')),
            '--i-table {}'.format(self.get_file('filtered_table')),
            '--p-sampling-depth {}'.format(self.config['sampling_depth']),
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--p-n-jobs {} '.format(self.num_jobs),
            '--output-dir {};'.format(self.get_file('core_metrics_results'))
        ]
        self.jobtext.append(' '.join(cmd))

    def alpha_diversity(self, metric='faith_pd'):
        """
        Run core diversity.
        metric : ('faith_pd' or 'evenness')
        """
        self.add_path('{}_group_significance'.format(metric), '.qzv')
        cmd = [
            'qiime diversity alpha-group-significance',
            '--i-alpha-diversity {}'.format(self.get_file('core_metrics_results') / '{}_vector.qza'.format(metric)),
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--o-visualization {}&'.format(self.get_file('{}_group_significance'.format(metric)))
        ]
        self.jobtext.append(' '.join(cmd))

    def beta_diversity(self, column='Nationality'):
        """
        Run core diversity.
        column: Some column from the metadata file
        """
        self.add_path('unweighted_{}_significance'.format(column), '.qzv')
        cmd = [
            'qiime diversity beta-group-significance',
            '--i-distance-matrix {}'.format(self.get_file('core_metrics_results') /
                                            'unweighted_unifrac_distance_matrix.qza'),
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--m-metadata-column {}'.format(column),
            '--o-visualization {}'.format(self.get_file('unweighted_{}_significance'.format(column))),
            '--p-pairwise&'
        ]
        self.jobtext.append(' '.join(cmd))

    def taxa_diversity(self):
        """ Create visualizations of taxa summaries at each level. """
        self.add_path('taxa_bar_plot', '.qzv')
        cmd = [
            'qiime taxa barplot',
            '--i-table {}'.format(self.get_file('filtered_table')),
            '--i-taxonomy {}'.format(self.get_file('taxonomy')),
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--o-visualization {}'.format(self.get_file('taxa_bar_plot'))
        ]
        self.jobtext.append(' '.join(cmd))

    def alpha_rarefaction(self, max_depth=4000):
        """
        Create plots for alpha rarefaction.
        """
        self.add_path('alpha_rarefaction', '.qzv')
        cmd = [
            'qiime diversity alpha-rarefaction',
            '--i-table {}'.format(self.get_file('filtered_table')),
            '--i-phylogeny {}'.format(self.get_file('rooted_tree')),
            '--p-max-depth {}'.format(max_depth),
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--o-visualization {}&'.format(self.get_file('alpha_rarefaction'))
        ]
        self.jobtext.append(' '.join(cmd))

    def classify_taxa(self, classifier):
        """
        Create plots for alpha rarefaction.
        """
        self.add_path('taxonomy', '.qza')
        cmd = [
            'qiime feature-classifier classify-sklearn',
            '--i-classifier {}'.format(classifier),
            '--i-reads {}'.format(self.get_file('rep_seqs_{}'.format(self.atype))),
            '--o-classification {}'.format(self.get_file('taxonomy')),
            '--p-n-jobs {}'.format(self.num_jobs)
        ]
        self.jobtext.append(' '.join(cmd))

    def add_pseudocount(self, category, level=None):
        """ Add composition pseudocount """
        if level is None:
            new_file = 'comp-{}-table'.format(category)
        else:
            new_file = 'comp-{}-table-l{}'.format(category, level)
        self.add_path(new_file, '.qza')
        cmd = [
            'qiime composition add-pseudocount',
            '--i-table {}'.format(self.get_file('filtered_table')),
            '--o-composition-table {}'.format(self.get_file(new_file))
        ]
        self.jobtext.append(' '.join(cmd))

    def composition_ancom(self, category, level=None):
        """ Add composition ancom """

        if level is None:
            new_file = 'ancom-{}'.format(category)
            infile = 'comp-{}-table'.format(category)
        else:
            new_file = 'ancom-{}-l{}'.format(category, level)
            infile = 'comp-{}-table-l{}'.format(category, level)

        self.add_path(new_file, '.qzv')
        cmd = [
            'qiime composition ancom',
            '--i-table {}'.format(self.get_file(infile)),
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--p-transform-function log',
            '--m-metadata-column {}'.format(category),
            '--o-visualization {}'.format(self.get_file(new_file))
        ]
        self.jobtext.append(' '.join(cmd))

    def taxa_collapse(self, category, taxa_level):
        """ Collapse taxonomy to the specified level """
        new_file = '{}_table_l{}'.format(category, taxa_level)
        self.add_path(new_file, '.qza')
        cmd = [
            'qiime taxa collapse',
            '--i-table {}'.format(self.get_file('filtered_table')),
            '--i-taxonomy {}'.format(self.get_file('taxonomy')),
            '--p-level {}'.format(taxa_level),
            '--o-collapsed-table {}'.format(self.get_file(new_file))
        ]
        self.jobtext.append(' '.join(cmd))

    def group_significance(self, category, level=None):
        """ Run all the commands related to calculating group_significance """
        log('Group sig: cat {} level {}'.format(category, level))
        if level is not None:
            self.taxa_collapse(category, level)
        self.add_pseudocount(category, level)
        self.composition_ancom(category, level)

    def sanity_check(self):
        """ Check that the counts after split_libraries and final counts match """
        log('Run sanity check on qiime2')
        log(self.files.keys())
        new_env = setup_environment('qiime2/2019.1')
        # Check the counts at the beginning of the analysis
        cmd = ['qiime', 'tools', 'export',
               '--input-path', str(self.files['demux_viz']),
               '--output-path', str(self.path / 'temp')]
        run(cmd, check=True, env=new_env)

        df = read_csv(self.path / 'temp' / 'per-sample-fastq-counts.csv', sep=',', header=0)
        initial_count = sum(df['Sequence count'])
        rmtree(self.path / 'temp')

        # Check the counts after DADA2/DeBlur
        cmd = ['qiime', 'tools', 'export',
               '--input-path', str(self.files['filtered_table']),
               '--output-path', str(self.path / 'temp')]
        run(cmd, check=True, env=new_env)
        log(cmd)

        cmd = ['biom', 'summarize-table', '-i', str(self.path / 'temp' / 'feature-table.biom')]
        result = run(cmd, capture_output=True, check=True, env=new_env)
        final_count = int(result.stdout.decode('utf-8').split('\n')[2].split(':')[1].strip().replace(',', ''))
        rmtree(self.path / 'temp')

        # Compare the difference
        if abs(initial_count - final_count) > 0.30 * (initial_count + final_count):
            message = 'Large difference ({}%) between initial and final counts'
            message = message.format(int(100 * (initial_count - final_count) /
                                         (initial_count + final_count)))
            log('Sanity check result')
            log(message)
            raise AnalysisError(message)

    def setup_analysis(self):
        """ Create the job file for the analysis. """
        mdf = load_metadata(self.files['metadata'])
        # Spawn the child jobs
        if not self.is_child:
            for col in self.config['metadata']:
                for val, df in mdf.groupby(col):
                    qiime = self.spawn_child_tool(col, val)
                    p = Process(target=run_analysis, args=(qiime,))
                    self.children.append(p)

        if 'demuxed' in self.data_type:
            self.unzip()
        self.qimport()
        if 'demuxed' not in self.data_type:
            self.demultiplex()
            self.demux_visualize()

        if self.atype == 'deblur':
            self.deblur_filter()
            self.deblur_denoise()
            self.deblur_visualize()
        elif self.atype == 'dada2':
            self.dada2()
            self.tabulate()

        # Run these commands sequentially
        self.filter_by_metadata()
        self.alignment_mafft()
        self.alignment_mask()
        self.phylogeny_fasttree()
        self.phylogeny_midpoint_root()
        self.core_diversity()

        # Run these commands in parallel
        self.alpha_diversity()
        for col in self.config['metadata']:
            self.beta_diversity(col)
        self.alpha_rarefaction()

        # Wait for them all to finish
        self.jobtext.append('wait')
        self.classify_taxa(STORAGE_DIR / 'classifier.qza')
        self.taxa_diversity()

        # Calculate group significance
        for col in self.config['metadata']:
            self.group_significance(col)
            # For the requested taxanomic levels
            for level in self.config['taxa_levels']:
                self.group_significance(col, level)
        self.jobtext.append('wait')

        # Create the summary of the analysis
        self.summary()

        # Define the job and error files
        jobfile = self.path / (self.run_id + '_job')
        self.add_path(jobfile, '.lsf', 'jobfile')
        error_log = self.path / self.run_id
        self.add_path(error_log, '.err', 'errorlog')

    def run(self):
        """ Perform some analysis. """
        try:
            self.setup_analysis()
            jobfile = self.files['jobfile']
            self.write_file_locations()
            if self.testing:
                # Open the jobfile to write all the commands
                jobfile.write_text('\n'.join(['#!/bin/bash -l'] + self.jobtext))
                # Set execute permissions
                jobfile.chmod(0o770)
                # Run the command
                run([jobfile], check=True)
            else:
                # Get the job header text from the template
                temp = JOB_TEMPLATE.read_text()
                # Write all the commands
                jobfile.write_text('\n'.join([temp.format(**self.get_job_params())] + self.jobtext))
                # Set execute permissions
                jobfile.chmod(0o770)
                #  Temporary for testing on Minerva
                run([jobfile], check=True)
                #  job_id = int(str(output.stdout).split(' ')[1].strip('<>'))
                #  self.wait_on_job(job_id)

            self.sanity_check()
            with Database(owner=self.owner, testing=self.testing) as db:
                doc = db.get_metadata(self.access_code)
            self.move_user_files()
            self.add_summary_files()
            while True:

            log('Send email')
            if not self.testing:
                send_email(doc.email,
                           doc.owner,
                           'analysis',
                           analysis_type='Qiime2 (2018.4) ' + self.atype,
                           study_name=doc.study,
                           summary=self.path / 'summary/analysis.pdf',
                           testing=self.testing)
        except CalledProcessError as e:
            self.move_user_files()
            self.write_file_locations()
            raise AnalysisError(e.args[0])
