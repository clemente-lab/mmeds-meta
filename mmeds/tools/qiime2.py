from subprocess import run
from shutil import rmtree
import pandas as pd

from mmeds.config import DATABASE_DIR
from mmeds.util import setup_environment, get_mapping_file_subset
from mmeds.error import AnalysisError
from mmeds.tools.tool import Tool
from mmeds.logging import Logger


class Qiime2(Tool):
    """ A class for qiime 2 analysis of uploaded studies. """

    # The default classifier for Q2 analysis
    classifier = DATABASE_DIR / 'gg-13-8-99-nb-classifier.qza'

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing,
                 sequencing_runs, run_on_node=False, analysis=True, restart_stage=0, kill_stage=-1, child=False):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing,
                         sequencing_runs, run_on_node=run_on_node, analysis=analysis, restart_stage=restart_stage,
                         kill_stage=kill_stage, child=child)
        if testing:
            load = 'module use {}/.modules/modulefiles; module load qiime2/2019.7;'.format(DATABASE_DIR.parent)
        else:
            load = 'export LC_ALL=en_US.UTF-8;\nml anaconda3;\nsource activate qiime2-2020.8.0;'
        self.module = load
        self.jobtext.append(load)

    # ============== #
    # Helper Methods #
    # ============== #

    def reads_type(self, run):
        """ Get reads type of current sequencing run """
        if 'reverse' in self.sequencing_runs[run]:
            return 'paired'
        return 'single'

    def barcodes_type(self, run):
        """ Get barcodes type of current sequencing run """
        if 'rev_barcodes' in self.sequencing_runs[run]:
            return 'dual'
        return 'single'

    # =============== #
    # Qiime2 Commands #
    # =============== #
    def source_activate(self, env):
        """ Change anaconda3 environment """
        # possible envs: ['qiime', 'pheniqs', 'mmeds']
        full_env = ''
        if env == 'qiime':
            full_env = 'qiime2-2020.8.0'
        elif env == 'mmeds':
            full_env = '/sc/arion/projects/MMEDS/admin_modules/mmeds-stable'
        else:
            full_env = env
        cmd = 'source activate {};'.format(full_env)
        self.jobtext.append(cmd)

    def split_by_sequencing_run(self):
        """ Separate metadata into sub-folders for each sequencing run """
        for run in self.sequencing_runs:
            # Create sequencing run folder
            self.add_path(self.path / f"section_{run}", key=f"section_{run}")
            run_dir = self.get_file(f"section_{run}", True)
            if not run_dir.is_dir():
                run_dir.mkdir()

            # Create sub-import folder
            self.add_path(run_dir / 'import_dir', key=f'working_dir_{run}')
            working_dir = self.get_file(f"working_dir_{run}", True)
            if not working_dir.is_dir():
                working_dir.mkdir()

            # Create symlinks to each file of each sequencing run
            for f in self.sequencing_runs[run]:
                self.add_path(working_dir / f"{f}", ".fastq.gz", key=f'{f}_{run}')
                self.get_file(f"{f}_{run}", True).symlink_to(self.sequencing_runs[run][f])

            # Create sub-mapping file that only includes samples for this sequencing run
            self.add_path(run_dir / f"qiime_mapping_file_{run}", ".tsv", key=f"mapping_{run}")
            df = get_mapping_file_subset(self.get_file("mapping", True), run)
            df.to_csv(self.get_file(f"mapping_{run}", True), sep='\t', index=False)

    def qimport(self, run, write=True):
        """ Split the libraries and perform quality analysis. """
        run_dir = self.get_file(f"section_{run}", True)

        self.add_path(run_dir / 'qiime_artifact.qza', key=f'demux_file_{run}')

        """
        if 'demuxed' in self.doc.reads_type:
            # If the reads are already demultiplexed import the whole directory
            cmd = [
                'qiime tools import ',
                '--type {} '.format('"SampleData[PairedEndSequencesWithQuality]"'),
                '--input-path {}'.format(self.get_file('for_reads')),
                '--input-format {}'.format('CasavaOneEightSingleLanePerSampleDirFmt'),
                '--output-path {};'.format(self.get_file('demux_file'))
            ]
            command = ' '.join(cmd)
        """

        # Create a directory to import as a Qiime2 object
        self.add_path(run_dir / 'qiime_artifact.qza', key=f'working_file_{run}')

        cmd = 'qiime tools import --type {} --input-path {} --output-path {};'
        if self.reads_type(run) == 'single':
            command = cmd.format('EMPSingleEndSequences',
                                 self.get_file(f'working_dir_{run}'),
                                 self.get_file(f'working_file_{run}'))
        elif self.barcodes_type(run) == 'single':
            command = cmd.format('EMPPairedEndSequences',
                                 self.get_file(f'working_dir_{run}'),
                                 self.get_file(f'working_file_{run}'))
        else:
            command = cmd.format('MultiplexedPairedEndBarcodeInSequence',
                                 self.get_file(f'working_dir_{run}'),
                                 self.get_file('working_file_{run}'))
        if write:
            self.jobtext.append(command)

    def qimport_demultiplexed(self, run):
        """ Import the demultiplexed dual_barcode files """
        cmd = [
            'qiime tools import',
            '--type {}'.format('"SampleData[PairedEndSequencesWithQuality]"'),
            '--input-path {}'.format(self.get_file(f'stripped_dir_{run}')),
            '--input-format {}'.format('CasavaOneEightSingleLanePerSampleDirFmt'),
            '--output-path {};'.format(self.get_file(f'demux_file_{run}'))
        ]
        self.jobtext.append(' '.join(cmd))

    def demultiplex(self, run):
        """
        Demultiplex the reads.
        NOTE: Great place to put a switch statement.
        """
        run_dir = self.get_file(f"section_{run}", True)

        # Add the otu directory to the MetaData object
        self.add_path(run_dir / 'demux_file', '.qza', key=f'demux_file_{run}')
        self.add_path(run_dir / 'error_correction', '.qza', key=f'error_correction_{run}')

        # Run the script
        if self.barcodes_type(run) == 'single':
            cmd = [
                # Either emp-single or emp-paired depending on the reads_type
                'qiime demux emp-{}'.format(self.reads_type(run)),
                '--i-seqs {}'.format(self.get_file(f'working_file_{run}')),
                '--m-barcodes-file {}'.format(self.get_file(f'mapping_{run}')),
                '--m-barcodes-column {}'.format('BarcodeSequence'),
                '--o-error-correction-details {}'.format(self.get_file(f'error_correction_{run}')),
                '--o-per-sample-sequences {};'.format(self.get_file(f'demux_file_{run}'))
            ]
            # Reverse compliment the barcodes in the mapping file if using paired reads
            if self.reads_type(run) == 'paired':
                cmd = cmd[:3] + ['--p-rev-comp-mapping-barcodes '] + cmd[3:]
            self.jobtext.append(' '.join(cmd))

        elif 'dual':
            self.add_path(run_dir / 'pheniqs_config', '.json', key=f'pheniqs_config_{run}')
            self.add_path(run_dir / 'pheniqs_output', key=f'pheniqs_dir_{run}')
            self.add_path(run_dir / 'stripped_output', key=f'stripped_dir_{run}')

            if not self.get_file(f'pheniqs_dir_{run}', True).is_dir():
                self.get_file(f'pheniqs_dir_{run}', True).mkdir()

            if not self.get_file(f'stripped_dir_{run}', True).is_dir():
                self.get_file(f'stripped_dir_{run}', True).mkdir()

            # Create pheniqs configuration file
            self.source_activate('mmeds')
            cmd = [
                'make_pheniqs_config.py',
                '--reads-forward {}'.format(self.get_file(f'forward_{run}')),
                '--reads-reverse {}'.format(self.get_file(f'reverse_{run}')),
                '--barcodes-forward {}'.format(self.get_file(f'barcodes_{run}')),
                '--barcodes-reverse {}'.format(self.get_file(f'rev_barcodes_{run}')),
                '--mapping-file {}'.format(self.get_file(f'mapping_{run}')),
                '--o-config {}'.format(self.get_file(f'pheniqs_config_{run}')),
                '--o-directory {};'.format(self.get_file(f'pheniqs_dir_{run}'))
            ]
            self.jobtext.append(' '.join(cmd))

            # Run pheniqs demultiplexing
            self.source_activate('pheniqs')
            cmd = 'pheniqs mux --config {};'.format(self.get_file(f'pheniqs_config_{run}'))
            self.jobtext.append(cmd)

            # Edit out pheniqs errors greater than --num-allowed-errors
            self.source_activate('mmeds')
            cmd = [
                'strip_error_barcodes.py',
                '--num-allowed-errors {}'.format(1),
                '--m-mapping-file {}'.format(self.get_file(f'mapping_{run}')),
                '--i-directory {}'.format(self.get_file(f'pheniqs_dir_{run}')),
                '--o-directory {};'.format(self.get_file(f'stripped_dir_{run}'))
            ]
            self.jobtext.append(' '.join(cmd))

            self.source_activate('qiime')

        # TODO: decide to permanently remove
        """
        elif 'dual_barcodes_legacy':
            self.add_path('unmatched_demuxed', '.qza')
            self.add_path('demux_log', '.txt')
            cmd = [
                'qiime cutadapt demux-paired',
                '--i-seqs {}'.format(self.get_file('working_file')),
                '--m-forward-barcodes-file {}'.format(self.get_file('mapping')),
                '--m-forward-barcodes-column {}'.format('BarcodeSequence'),
                '--m-reverse-barcodes-file {}'.format(self.get_file('mapping')),
                '--m-reverse-barcodes-column {}'.format('BarcodeSequenceR'),
                '--o-per-sample-sequences {}'.format(self.get_file('demux_file')),
                '--o-untrimmed-sequences {}'.format(self.get_file('unmatched_demuxed')),
                '--p-error-rate 0.3',
                '--verbose &> {}'.format(self.get_file('demux_log'))
            ]

            self.jobtext.append(' '.join(cmd))
        """

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

    def filter_visualize(self):
        """ Create visualization summary for the filtered table """
        self.add_path('filtered_viz', '.qzv')

        cmd = [
            'qiime feature-table summarize',
            '--i-table {}'.format(self.get_file('filtered_table')),
            '--o-visualization {}'.format(self.get_file('filtered_viz'))
        ]
        self.jobtext.append(' '.join(cmd))

    def demux_visualize(self, run):
        """ Create visualization summary for the demux file. """
        run_dir = self.get_file(f"section_{run}", True)
        self.add_path(run_dir / 'demux_viz', '.qzv', key=f"demux_viz_{run}")

        # Run the script
        cmd = [
            'qiime demux summarize',
            '--i-data {}'.format(self.get_file(f'demux_file_{run}')),
            '--o-visualization {};'.format(self.get_file(f'demux_viz_{run}'))
        ]
        self.jobtext.append(' '.join(cmd))

    def merge_runs(self):
        """ Merge sequences and tables of individual sequencing runs """
        self.add_path('otu_table', '.qzv')
        self.add_path('rep_seqs_table', '.qza')

        tables = []
        seqs = []
        for run in self.sequencing_runs:
            tables.append(str(self.get_file(f"otu_table_{run}")))
            seqs.append(str(self.get_file(f"rep_seqs_table_{run}")))

        cmd = [
            'qiime feature-table merge',
            '--i-tables {}'.format(' '.join(tables)),
            '--o-merged-table {}'.format(self.get_file('otu_table'))
        ]
        self.jobtext.append(' '.join(cmd))

        cmd = [
            'qiime feature-table merge-seqs',
            '--i-data {}'.format(' '.join(seqs)),
            '--o-merged-data {}'.format(self.get_file('rep_seqs_table'))
        ]
        self.jobtext.append(' '.join(cmd))

    def tabulate(self, run):
        """ Run tabulate visualization. """
        run_dir = self.get_file(f"section_{run}", True)

        self.add_path(run_dir / 'stats_{}_visual'.format(self.doc.analysis_type), '.qzv', key=f'stats_visual_{run}')

        cmd = [
            'qiime metadata tabulate',
            '--m-input-file {}'.format(self.get_file(f'stats_table_{run}')),
            '--o-visualization {};'.format(self.get_file(f'stats_visual_{run}'))
        ]
        self.jobtext.append(' '.join(cmd))

    def dada2(self, run, p_trim_left=0, p_trunc_len=0):
        """ Run DADA2 analysis on the demultiplexed file. """
        run_dir = self.get_file(f"section_{run}", True)

        # Index new files
        self.add_path(run_dir / 'rep_seqs_dada2', '.qza', key=f'rep_seqs_table_{run}')
        self.add_path(run_dir / 'table_dada2', '.qza', key=f'otu_table_{run}')
        self.add_path(run_dir / 'stats_dada2', '.qza', key=f'stats_table_{run}')

        if self.reads_type(run) == 'single':
            cmd = [
                'qiime dada2 denoise-single',
                '--i-demultiplexed-seqs {}'.format(self.get_file(f'demux_file_{run}')),
                '--p-trim-left {}'.format(p_trim_left),
                '--p-trunc-len {}'.format(p_trunc_len),
                '--o-representative-sequences {}'.format(self.get_file(f'rep_seqs_table_{run}')),
                '--o-table {}'.format(self.get_file(f'otu_table_{run}')),
                '--o-denoising-stats {}'.format(self.get_file(f'stats_table_{run}')),
                '--p-n-threads {};'.format(self.num_jobs)
            ]
        else:
            cmd = [
                'qiime dada2 denoise-paired',
                '--i-demultiplexed-seqs {}'.format(self.get_file(f'demux_file_{run}')),
                '--p-trim-left-f {}'.format(p_trim_left),
                '--p-trim-left-r {}'.format(p_trim_left),
                '--p-trunc-len-f {}'.format(p_trunc_len),
                '--p-trunc-len-r {}'.format(p_trunc_len),
                '--o-representative-sequences {}'.format(self.get_file(f'rep_seqs_table_{run}')),
                '--o-table {}'.format(self.get_file(f'otu_table_{run}')),
                '--o-denoising-stats {}'.format(self.get_file(f'stats_table_{run}')),
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
            '--o-filter-stats {}'.format(self.get_file('demux_filter_stats')),
            '--quiet;'
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
            '--o-stats {}'.format(self.get_file('stats_table')),
            '--quiet;'
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_visualize(self):
        """ Create visualizations from deblur analysis. """
        self.add_path('stats_deblur_visual', '.qzv')
        cmd = [
            'qiime deblur visualize-stats',
            '--i-deblur-stats {}'.format(self.get_file('stats_table')),
            '--o-visualization {}'.format(self.get_file('stats_deblur_visual')),
            '--quiet;'
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
            '--p-n-jobs-or-threads {} '.format(self.num_jobs),
            '--output-dir {};'.format(self.get_file('core_metrics_results'))
        ]
        self.jobtext.append(' '.join(cmd))

    def alpha_diversity(self, metrics=['faith_pd', 'shannon', 'observed_features', 'evenness']):
        """
        Run core diversity.
        metric : ('faith_pd' 'shannon', or 'observed_features', 'evenness')
        """
        for metric in metrics:
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

    def taxa_diversity(self, category=None):
        """ Create visualizations of taxa summaries at each level. """
        if not category:
            # Create taxa visualization for entire dataset
            taxa_bar_plot = 'taxa_bar_plot'
            table = 'filtered_table'
            mapping = 'mapping'
        else:
            # Create taxa visualization averaged for metadata category
            taxa_bar_plot = 'grouped_{}_taxa_bar_plot'.format(category)
            table = 'grouped_{}_table'.format(category)
            mapping = 'grouped_{}_mapping_file'.format(category)
        self.add_path(taxa_bar_plot, '.qzv')
        cmd = [
            'qiime taxa barplot',
            '--i-table {}'.format(self.get_file(table)),
            '--i-taxonomy {}'.format(self.get_file('taxonomy')),
            '--m-metadata-file {}'.format(self.get_file(mapping)),
            '--o-visualization {}'.format(self.get_file(taxa_bar_plot))
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

    def classify_taxa(self):
        """
        Create plots for alpha rarefaction.
        """
        self.add_path('taxonomy', '.qza')
        cmd = [
            'qiime feature-classifier classify-sklearn',
            '--i-classifier {}'.format(self.classifier),
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
        if level is not None:
            self.taxa_collapse(category, level)
        self.add_pseudocount(category, level)
        self.composition_ancom(category, level)

    def group_feature_table(self, category):
        """ Group feature table by specified metadata category """
        new_file = 'grouped_{}_table'.format(category)
        self.add_path(new_file, '.qza')
        cmd = [
            'qiime feature-table group',
            '--i-table {}'.format(self.get_file('filtered_table')),
            '--p-axis \'sample\'',
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--m-metadata-column {}'.format(category),
            '--p-mode \'mean-ceiling\'',
            '--o-grouped-table {};'.format(self.get_file(new_file))
        ]
        self.jobtext.append(' '.join(cmd))

    def group_mapping_file(self, category):
        """ Run script to create grouped mapping file """
        new_file = 'grouped_{}_mapping_file'.format(category)
        self.add_path(new_file, '.tsv')
        cmd = [
            'make_grouped_mapping_file.py',
            '--m-metadata-file {}'.format(self.get_file('mapping')),
            '--m-metadata-column {}'.format(category),
            '--o-grouped-metadata-file {};'.format(self.get_file(new_file))
        ]
        self.jobtext.append(' '.join(cmd))

    def mean_taxa(self, cols, cols_continuous):
        """ Run all commands relating to calculating group mean taxa bar plots """
        categories = [col for col in cols if not cols_continuous[col]]
        if categories:
            self.source_activate('mmeds')
            for cat in categories:
                self.group_mapping_file(cat)
            self.source_activate('qiime')
            for cat in categories:
                self.group_feature_table(cat)
                self.taxa_diversity(cat)

    def sanity_check(self):
        """ Check that the counts after split_libraries and final counts match """
        Logger.debug('Run sanity check on qiime2')
        Logger.debug(self.doc.keys())
        new_env = setup_environment('qiime2/2019.1')
        # Check the counts at the beginning of the analysis
        cmd = ['qiime', 'tools', 'export',
               '--input-path', str(self.get_file('demux_viz', True)),
               '--output-path', str(self.path / 'temp')]
        run(cmd, check=True, env=new_env)

        df = pd.read_csv(self.path / 'temp' / 'per-sample-fastq-counts.csv', sep=',', header=0)
        initial_count = sum(df['Sequence count'])
        rmtree(self.path / 'temp')

        # Check the counts after DADA2/DeBlur
        cmd = ['qiime', 'tools', 'export',
               '--input-path', str(self.get_file('filtered_table', True)),
               '--output-path', str(self.path / 'temp')]
        run(cmd, check=True, env=new_env)
        Logger.debug(cmd)

        cmd = ['biom', 'summarize-table', '-i', str(self.path / 'temp' / 'feature-table.biom')]
        result = run(cmd, capture_output=True, check=True, env=new_env)
        final_count = int(result.stdout.decode('utf-8').split('\n')[2].split(':')[1].strip().replace(',', ''))
        rmtree(self.path / 'temp')

        # Compare the difference
        if abs(initial_count - final_count) > 0.30 * (initial_count + final_count):
            message = 'Large difference ({}%) between initial and final counts'
            message = message.format(int(100 * (initial_count - final_count) /
                                         (initial_count + final_count)))
            Logger.debug('Sanity check result')
            Logger.debug(message)
            raise AnalysisError(message)

    def setup_stage_0(self):
        self.set_stage(0)
        self.split_by_sequencing_run()
        # Only the primary analysis runs these commands
        if not self.doc.sub_analysis:
            # TODO: Re-introduce already-demuxed functionality
            """
            if 'demuxed' in self.doc.reads_type:
                self.unzip()
            """
            for run in self.sequencing_runs:
                if self.barcodes_type(run) == 'dual':
                    self.qimport(run, False)
                    self.demultiplex(run)
                    self.qimport_demultiplexed(run)
                else:
                    self.qimport(run, True)

    def setup_stage_1(self):
        self.set_stage(1)
        if not self.doc.sub_analysis:
            for run in self.sequencing_runs:
                if not self.barcodes_type(run) == 'dual':
                    self.demultiplex(run)
                    self.demux_visualize(run)
                if 'deblur' == self.doc.analysis_type:
                    self.deblur_filter()
                    self.deblur_denoise()
                    self.deblur_visualize()
                elif 'dada2' == self.doc.analysis_type:
                    self.dada2(run)
                    self.tabulate(run)
                if self.kill_stage == 1:
                    self.jobtext.append('exit 1')
            self.merge_runs()
        else:
            del self.jobtext[-1]

    def setup_stage_2(self):
        self.set_stage(2)
        # Run these commands sequentially
        self.filter_by_metadata()
        self.filter_visualize()
        self.alignment_mafft()
        self.alignment_mask()
        self.phylogeny_fasttree()
        self.phylogeny_midpoint_root()
        self.core_diversity()
        if self.kill_stage == 2:
            self.jobtext.append('exit 2')

    def setup_stage_3(self):
        self.set_stage(3)
        # Run these commands in parallel
        self.alpha_diversity()
        for col in self.doc.config['metadata']:
            # Don't run on continuous columns
            if not self.doc.config['metadata_continuous'][col]:
                self.beta_diversity(col)
        self.alpha_rarefaction()

        # Wait for them all to finish
        self.jobtext.append('wait')
        if self.kill_stage == 3:
            self.jobtext.append('exit 3')

    def setup_stage_4(self):
        self.set_stage(4)
        self.classify_taxa()
        self.taxa_diversity()
        # Calculate group significance
        for col in self.doc.config['metadata']:
            # Do not group if the metadata is continuous
            if not self.doc.config['metadata_continuous'][col]:
                self.group_significance(col)
                # For the requested taxanomic levels
                for level in self.doc.config['taxa_levels']:
                    self.group_significance(col, level)
        # Calculate mean taxas
        self.mean_taxa(self.doc.config['metadata'], self.doc.config['metadata_continuous'])
        self.jobtext.append('wait')
        if self.kill_stage == 4:
            self.jobtext.append('exit 4')

    def setup_analysis(self, summary=True):
        """ Create the job file for the analysis. """
        if self.restart_stage < 1:
            self.setup_stage_0()
        if self.restart_stage < 2:
            self.setup_stage_1()
        if self.restart_stage < 3:
            self.setup_stage_2()
        if self.restart_stage < 4:
            self.setup_stage_3()
        if self.restart_stage < 5:
            self.setup_stage_4()
        if self.restart_stage < 6:
            self.set_stage(5)
        # Perform standard tool setup
        super().setup_analysis(summary=summary)
