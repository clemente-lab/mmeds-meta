from subprocess import run
from shutil import rmtree
from pandas import read_csv

from mmeds.config import STORAGE_DIR, DATABASE_DIR
from mmeds.util import log, setup_environment
from mmeds.error import AnalysisError
from mmeds.tool import Tool


class Qiime2(Tool):
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing,
                 analysis=True, restart_stage=0):
        super().__init__(owner, access_code, atype, config, testing,
                         analysis=analysis, restart_stage=restart_stage)
        load = 'module use {}/.modules/modulefiles; module load qiime2/2019.1;'.format(DATABASE_DIR.parent)
        self.jobtext.append(load)
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))
        self.module = load

    # =============== #
    # Qiime2 Commands #
    # =============== #
    def qimport(self):
        """ Split the libraries and perform quality analysis. """

        self.add_path(self.path / 'qiime_artifact.qza', key='demux_file')

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
        else:
            # Create a directory to import as a Qiime2 object
            self.add_path(self.path / 'import_dir', key='working_dir')
            self.add_path(self.path / 'qiime_artifact.qza', key='working_file')

            if not self.get_file('working_dir', True).is_dir():
                self.get_file('working_dir', True).mkdir()

            # Clean up any existing files
            old_files = self.get_file('working_dir', True).glob('*')
            for old_file in old_files:
                old_file.unlink()

            # Link the barcodes
            (self.get_file('working_dir', True) / 'barcodes.fastq.gz').symlink_to(self.get_file('barcodes', True))
            if self.data_type == 'single_end':
                # Create links to the data in the qiime2 import directory
                (self.get_file('working_dir', True) / 'sequences.fastq.gz').symlink_to(self.get_file('for_reads', True))

                # Run the script
                cmd = 'qiime tools import --type {} --input-path {} --output-path {};'
                command = cmd.format('EMPSingleEndSequences',
                                     self.get_file('working_dir'),
                                     self.get_file('working_file'))
            elif self.data_type == 'paired_end':
                # Create links to the data in the qiime2 import directory
                (self.get_file('working_dir', True) / 'forward.fastq.gz').symlink_to(self.get_file('for_reads', True))
                (self.get_file('working_dir', True) / 'reverse.fastq.gz').symlink_to(self.get_file('rev_reads', True))

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
            '--i-table {}'.format(self.get_file('otu_table')),
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
        self.add_path('stats_{}_visual'.format(self.doc.analysis_type.split('-')[1], '.qzv'))
        cmd = [
            'qiime metadata tabulate',
            '--m-input-file {}'.format(self.get_file('stats_table')),
            '--o-visualization {};'.format(self.get_file('stats_{}_visual'.format(self.doc.analysis_type.split('-')[1])))
        ]
        self.jobtext.append(' '.join(cmd))

    def dada2(self, p_trim_left=0, p_trunc_len=0):
        """ Run DADA2 analysis on the demultiplexed file. """
        # Index new files
        self.add_path('rep_seqs_dada2', '.qza', key='rep_seqs_table')
        self.add_path('table_dada2', '.qza', key='otu_table')
        self.add_path('stats_dada2', '.qza', key='stats_table')

        if 'single' in self.data_type:
            cmd = [
                'qiime dada2 denoise-single',
                '--i-demultiplexed-seqs {}'.format(self.get_file('demux_file')),
                '--p-trim-left {}'.format(p_trim_left),
                '--p-trunc-len {}'.format(p_trunc_len),
                '--o-representative-sequences {}'.format(self.get_file('rep_seqs_table')),
                '--o-table {}'.format(self.get_file('otu_table')),
                '--o-denoising-stats {}'.format(self.get_file('stats_table')),
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
                '--o-representative-sequences {}'.format(self.get_file('rep_seqs_table')),
                '--o-table {}'.format(self.get_file('otu_table')),
                '--o-denoising-stats {}'.format(self.get_file('stats_table')),
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
        self.add_path('rep_seqs_deblur', '.qza', key='rep_seqs_table')
        self.add_path('table_deblur', '.qza', key='otu_table')
        self.add_path('stats_deblur', '.qza', key='stats_table')
        cmd = [
            'qiime deblur denoise-16S',
            '--i-demultiplexed-seqs {}'.format(self.get_file('demux_filtered')),
            '--p-trim-length {}'.format(p_trim_length),
            '--o-representative-sequences {}'.format(self.get_file('rep_seqs_table')),
            '--o-table {}'.format(self.get_file('otu_table')),
            '--p-sample-stats',
            '--p-jobs-to-start {}'.format(self.num_jobs),
            '--o-stats {};'.format(self.get_file('stats_table')),
            '--quiet'
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_visualize(self):
        """ Create visualizations from deblur analysis. """
        self.add_path('stats_deblur_visual', '.qzv')
        cmd = [
            'qiime deblur visualize-stats',
            '--i-deblur-stats {}'.format(self.get_file('stats_table')),
            '--o-visualization {};'.format(self.get_file('stats_deblur_visual')),
            '--quiet'
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mafft(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 1"""
        self.add_path('alignment', '.qza')
        cmd = [
            'qiime alignment mafft',
            '--i-sequences {}'.format(self.get_file('rep_seqs_table')),
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
            '--p-sampling-depth {}'.format(self.doc.config['sampling_depth']),
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
            '--i-reads {}'.format(self.get_file('rep_seqs_table')),
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
        log(self.doc.keys())
        new_env = setup_environment('qiime2/2019.1')
        # Check the counts at the beginning of the analysis
        cmd = ['qiime', 'tools', 'export',
               '--input-path', str(self.get_file('demux_viz', True)),
               '--output-path', str(self.path / 'temp')]
        run(cmd, check=True, env=new_env)

        df = read_csv(self.path / 'temp' / 'per-sample-fastq-counts.csv', sep=',', header=0)
        initial_count = sum(df['Sequence count'])
        rmtree(self.path / 'temp')

        # Check the counts after DADA2/DeBlur
        cmd = ['qiime', 'tools', 'export',
               '--input-path', str(self.get_file('filtered_table', True)),
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
        if self.restart_stage < 2:
            self.jobtext.append('echo "MMEDS_STAGE_1"')
            # Only the primary analysis runs these commands
            if not self.doc.sub_analysis:
                if 'demuxed' in self.data_type:
                    self.unzip()
                self.qimport()
                if 'demuxed' not in self.data_type:
                    self.demultiplex()
                    self.demux_visualize()

                if 'deblur' in self.doc.analysis_type:
                    self.deblur_filter()
                    self.deblur_denoise()
                    self.deblur_visualize()
                elif 'dada2' in self.doc.analysis_type:
                    self.dada2()
                    self.tabulate()

        if self.restart_stage < 3:
            self.jobtext.append('echo "MMEDS_STAGE_2"')
            # Run these commands sequentially
            self.filter_by_metadata()
            self.alignment_mafft()
            self.alignment_mask()
            self.phylogeny_fasttree()
            self.phylogeny_midpoint_root()
            self.core_diversity()

        if self.restart_stage < 4:
            self.jobtext.append('echo "MMEDS_STAGE_3"')
            # Run these commands in parallel
            self.alpha_diversity()
            for col in self.doc.config['metadata']:
                self.beta_diversity(col)
            self.alpha_rarefaction()

            # Wait for them all to finish
            self.jobtext.append('wait')

        if self.restart_stage < 5:
            self.jobtext.append('echo "MMEDS_STAGE_4"')
            self.classify_taxa(STORAGE_DIR / 'classifier.qza')
            self.taxa_diversity()
            # Calculate group significance
            for col in self.doc.config['metadata']:
                self.group_significance(col)
                # For the requested taxanomic levels
                for level in self.doc.config['taxa_levels']:
                    self.group_significance(col, level)
            self.jobtext.append('wait')

        if self.restart_stage < 6:
            self.jobtext.append('echo "MMEDS_STAGE_5"')
            # Perform standard tool setup
            super().setup_analysis()
