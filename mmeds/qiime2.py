from subprocess import run, CalledProcessError, PIPE
from shutil import rmtree
from pandas import read_csv

from mmeds.config import JOB_TEMPLATE, STORAGE_DIR
from mmeds.mmeds import send_email, log
from mmeds.error import AnalysisError
from mmeds.tool import Tool


class Qiime2(Tool):
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing):
        super().__init__(owner, access_code, atype, config, testing)
        if testing:
            self.jobtext.append('module use ~/.modules/modulefiles; module load qiime2;')
        else:
            self.jobtext.append('; '.join(['module use $MMEDS/.modules/modulefiles',
                                           'module use /hpc/packages/minerva-common/modulefiles',
                                           'module load qiime2/2018.4;']))

    # ======================= #
    # # # Qiime2 Commands # # #
    # ======================= #
    def qimport(self):
        """ Split the libraries and perform quality analysis. """

        self.files['demux_file'] = self.path / 'qiime_artifact.qza'

        if 'demuxed' in self.data_type:
            # If the reads are already demultiplexed import the whole directory
            cmd = [
                'qiime tools import ',
                '--type {} '.format('"SampleData[PairedEndSequencesWithQuality]"'),
                '--input-path {}'.format(self.files['for_reads']),
                '--source-format {}'.format('CasavaOneEightSingleLanePerSampleDirFmt'),
                '--output-path {};'.format(self.files['demux_file'])
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
            command = cmd.format('EMPSingleEndSequences', self.files['working_dir'], self.files['working_file'])
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
            command = cmd.format('EMPPairedEndSequences', self.files['working_dir'], self.files['working_file'])
        self.jobtext.append(command)

    def demultiplex(self):
        """ Demultiplex the reads. """
        # Add the otu directory to the MetaData object
        self.add_path('demux_file', '.qza')

        # Run the script
        cmd = [
            # Either emp-single or emp-paired depending on the data_type
            'qiime demux emp-{}'.format(self.data_type.split('_')[0]),
            '--i-seqs {}'.format(self.files['working_file']),
            '--m-barcodes-file {}'.format(self.files['mapping']),
            '--m-barcodes-column {}'.format('BarcodeSequence'),
            '--o-per-sample-sequences {};'.format(self.files['demux_file'])
        ]
        self.jobtext.append(' '.join(cmd))

    def demux_visualize(self):
        """ Create visualization summary for the demux file. """
        self.add_path('demux_viz', '.qzv')

        # Run the script
        cmd = [
            'qiime demux summarize',
            '--i-data {}'.format(self.files['demux_file']),
            '--o-visualization {};'.format(self.files['demux_viz'])
        ]
        self.jobtext.append(' '.join(cmd))

    def tabulate(self):
        """ Run tabulate visualization. """
        self.add_path('stats_{}_visual'.format(self.atype), '.qzv')
        cmd = [
            'qiime metadata tabulate',
            '--m-input-file {}'.format(self.files['stats_{}'.format(self.atype)]),
            '--o-visualization {};'.format(self.files['stats_{}_visual'.format(self.atype)])
        ]
        self.jobtext.append(' '.join(cmd))

    def dada2(self, p_trim_left=0, p_trunc_len=120):
        """ Run DADA2 analysis on the demultiplexed file. """
        # Index new files
        self.add_path('rep_seqs_dada2', '.qza')
        self.add_path('table_dada2', '.qza')
        self.add_path('stats_dada2', '.qza')

        if 'single' in self.data_type:
            cmd = [
                'qiime dada2 denoise-single',
                '--i-demultiplexed-seqs {}'.format(self.files['demux_file']),
                '--p-trim-left {}'.format(p_trim_left),
                '--p-trunc-len {}'.format(p_trunc_len),
                '--o-representative-sequences {}'.format(self.files['rep_seqs_dada2']),
                '--o-table {}'.format(self.files['table_dada2']),
                '--o-denoising-stats {}'.format(self.files['stats_dada2']),
                '--p-n-threads {};'.format(self.num_jobs)
            ]
        elif 'paired' in self.data_type:
            cmd = [
                'qiime dada2 denoise-paired',
                '--i-demultiplexed-seqs {}'.format(self.files['demux_file']),
                '--p-trim-left-f {}'.format(p_trim_left),
                '--p-trim-left-r {}'.format(p_trim_left),
                '--p-trunc-len-f {}'.format(p_trunc_len),
                '--p-trunc-len-r {}'.format(p_trunc_len),
                '--o-representative-sequences {}'.format(self.files['rep_seqs_dada2']),
                '--o-table {}'.format(self.files['table_dada2']),
                '--o-denoising-stats {}'.format(self.files['stats_dada2']),
                '--p-n-threads {};'.format(self.num_jobs)
            ]
        self.jobtext.append(' '.join(cmd))

    def deblur_filter(self):
        """ Run Deblur analysis on the demultiplexed file. """
        self.add_path('demux_filtered', '.qza')
        self.add_path('demux_filter_stats', '.qza')
        cmd = [
            'qiime quality-filter q-score',
            '--i-demux {}'.format(self.files['demux_file']),
            '--o-filtered-sequences {}'.format(self.files['demux_filtered']),
            '--o-filter-stats {};'.format(self.files['demux_filter_stats']),
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
            '--i-demultiplexed-seqs {}'.format(self.files['demux_filtered']),
            '--p-trim-length {}'.format(p_trim_length),
            '--o-representative-sequences {}'.format(self.files['rep_seqs_deblur']),
            '--o-table {}'.format(self.files['table_deblur']),
            '--p-sample-stats',
            '--p-jobs-to-start {}'.format(self.num_jobs),
            '--o-stats {};'.format(self.files['stats_deblur']),
            '--quiet'
        ]
        self.jobtext.append(' '.join(cmd))

    def deblur_visualize(self):
        """ Create visualizations from deblur analysis. """
        self.add_path('stats_deblur_visual', '.qzv')
        cmd = [
            'qiime deblur visualize-stats',
            '--i-deblur-stats {}'.format(self.files['stats_deblur']),
            '--o-visualization {};'.format(self.files['stats_deblur_visual']),
            '--quiet'
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mafft(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 1"""
        self.add_path('alignment', '.qza')
        cmd = [
            'qiime alignment mafft',
            '--i-sequences {}'.format(self.files['rep_seqs_{}'.format(self.atype)]),
            '--o-alignment {};'.format(self.files['alignment'])
        ]
        self.jobtext.append(' '.join(cmd))

    def alignment_mask(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 2"""
        self.add_path('masked_alignment', '.qza')
        cmd = [
            'qiime alignment mask',
            '--i-alignment {}'.format(self.files['alignment']),
            '--o-masked-alignment {};'.format(self.files['masked_alignment'])
        ]
        self.jobtext.append(' '.join(cmd))

    def phylogeny_fasttree(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 3"""
        self.add_path('unrooted_tree', '.qza')
        cmd = [
            'qiime phylogeny fasttree',
            '--i-alignment {}'.format(self.files['masked_alignment']),
            '--o-tree {};'.format(self.files['unrooted_tree'])
        ]
        self.jobtext.append(' '.join(cmd))

    def phylogeny_midpoint_root(self):
        """ Generate a tree for phylogenetic diversity analysis. Step 4"""
        self.add_path('rooted_tree', '.qza')
        cmd = [
            'qiime phylogeny midpoint-root',
            '--i-tree {}'.format(self.files['unrooted_tree']),
            '--o-rooted-tree {};'.format(self.files['rooted_tree'])
        ]
        self.jobtext.append(' '.join(cmd))

    def core_diversity(self):
        """ Run core diversity """
        self.add_path('core_metrics_results', '')
        cmd = [
            'qiime diversity core-metrics-phylogenetic',
            '--i-phylogeny {}'.format(self.files['rooted_tree']),
            '--i-table {}'.format(self.files['table_{}'.format(self.atype)]),
            '--p-sampling-depth {}'.format(self.config['sampling_depth']),
            '--m-metadata-file {}'.format(self.files['mapping']),
            '--p-n-jobs {} '.format(self.num_jobs),
            '--output-dir {};'.format(self.files['core_metrics_results'])
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
            '--i-alpha-diversity {}'.format(self.files['core_metrics_results'] / '{}_vector.qza'.format(metric)),
            '--m-metadata-file {}'.format(self.files['mapping']),
            '--o-visualization {}&'.format(self.files['{}_group_significance'.format(metric)])
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
            '--i-distance-matrix {}'.format(self.files['core_metrics_results'] /
                                            'unweighted_unifrac_distance_matrix.qza'),
            '--m-metadata-file {}'.format(self.files['mapping']),
            '--m-metadata-column {}'.format(column),
            '--o-visualization {}'.format(self.files['unweighted_{}_significance'.format(column)]),
            '--p-pairwise&'
        ]
        self.jobtext.append(' '.join(cmd))

    def taxa_diversity(self):
        """ Create visualizations of taxa summaries at each level. """
        self.add_path('taxa_bar_plot', '.qzv')
        cmd = [
            'qiime taxa barplot',
            '--i-table {}'.format(self.files['table_{}'.format(self.atype)]),
            '--i-taxonomy {}'.format(self.files['taxonomy']),
            '--m-metadata-file {}'.format(self.files['mapping']),
            '--o-visualization {}'.format(self.files['taxa_bar_plot'])
        ]
        self.jobtext.append(' '.join(cmd))

    def alpha_rarefaction(self, max_depth=4000):
        """
        Create plots for alpha rarefaction.
        """
        self.add_path('alpha_rarefaction', '.qzv')
        cmd = [
            'qiime diversity alpha-rarefaction',
            '--i-table {}'.format(self.files['table_{}'.format(self.atype)]),
            '--i-phylogeny {}'.format(self.files['rooted_tree']),
            '--p-max-depth {}'.format(max_depth),
            '--m-metadata-file {}'.format(self.files['mapping']),
            '--o-visualization {}&'.format(self.files['alpha_rarefaction'])
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
            '--i-reads {}'.format(self.files['rep_seqs_{}'.format(self.atype)]),
            '--o-classification {}'.format(self.files['taxonomy']),
            '--p-n-jobs {}'.format(self.num_jobs)
        ]
        self.jobtext.append(' '.join(cmd))

    def sanity_check(self):
        """ Check that the counts after split_libraries and final counts match """
        log('Run sanity check on qiime2')
        log(self.files.keys())
        # Check the counts at the beginning of the analysis
        cmd = 'conda run -n {} qiime tools export {} --output-dir {}'.format(self.jobtext[0].split(' ')[-1],
                                                                             self.files['demux_viz'],
                                                                             self.path / 'temp')
        run(['bash'] + cmd.split(' '), shell=True, check=True)

        df = read_csv(self.path / 'temp' / 'per-sample-fastq-counts.csv', sep=',', header=0)
        initial_count = sum(df['Sequence count'])
        rmtree(self.path / 'temp')

        # Check the counts after DADA2/DeBlur
        cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                self.files['table_{}'.format(self.atype)],
                                                                self.path / 'temp')
        run('bash -c "{}"'.format(cmd), check=True)
        log(cmd)

        cmd = 'conda run -n {} biom summarize-table -i {}'.format(self.jobtext[0].split(' ')[-1],
                                                                  self.path / 'temp' / 'feature-table.biom')
        result = run(['bash'] + cmd.split(' '), stdout=PIPE, stderr=PIPE)
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
        self.summary()
        log('\n'.join(self.jobtext))

    def run(self):
        """ Perform some analysis. """
        try:
            if self.analysis:
                self.setup_analysis()
                jobfile = self.path / (self.run_id + '_job')
                self.add_path(jobfile, 'lsf')
                error_log = self.path / self.run_id
                self.add_path(error_log, 'err')
                self.write_file_locations()
                if self.testing:
                    # Open the jobfile to write all the commands
                    with open(str(jobfile) + '.lsf', 'w') as f:
                        f.write('#!/bin/bash -l\n')
                        f.write('\n'.join(self.jobtext))
                    # Run the command
                    output = run(['bash', '{}.lsf'.format(jobfile)],
                                 stdout=PIPE,
                                 stderr=PIPE,
                                 shell=True,
                                 check=True)
                    log(output.stdout.decode('utf-8').replace('\\n', '\n'))
                    log(output.stderr.decode('utf-8').replace('\\n', '\n'))
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
                    # output = run('bsub < {}.lsf'.format(jobfile), stdout=PIPE, shell=True, check=True)
                    output = run(['bash', '{}.lsf'.format(jobfile)], stdout=PIPE, check=True)
                    log(output)
                    #job_id = int(output.stdout.decode('utf-8').split(' ')[1].strip('<>'))
                    #self.wait_on_job(job_id)

            self.sanity_check()
            doc = self.db.get_metadata(self.access_code)
            self.move_user_files()
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
