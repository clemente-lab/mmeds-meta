from pathlib import Path
from subprocess import run, CalledProcessError, PIPE
from shutil import copy, rmtree, make_archive
from time import sleep
from pandas import read_csv
from collections import defaultdict
from multiprocessing import Process

from mmeds.database import Database
from mmeds.config import JOB_TEMPLATE, STORAGE_DIR
from mmeds.mmeds import send_email, log
from mmeds.authentication import get_email
from mmeds.error import AnalysisError
from mmeds.summarize import summarize


class Tool:
    """ The base class for tools used by mmeds """

    def __init__(self, owner, access_code, atype, config, testing, threads=10, analysis=True):
        """
        Setup the Tool class
        ====================
        :owner: A string. The owner of the files being analyzed.
        :access_code: A string. The code for accessing the files to be analyzed.
        :atype: A string. The type of analysis to perform. Qiime1 or 2, DADA2 or DeBlur.
        :config: A file object. A custom config file, may be None.
        :testing: A boolean. If True run with configurations for a local server.
        :threads: An int. The number of threads to use during analysis, is overwritten if testing==True.
        :analysis: A boolean. If True run a new analysis, if false just summarize the previous analysis.
        """
        log('Start analysis')
        self.db = Database('', owner=owner, testing=testing)
        self.access_code = access_code
        files, path = self.db.get_mongo_files(self.access_code)
        self.testing = testing
        self.jobtext = []
        self.owner = owner
        if testing:
            self.num_jobs = 3
        else:
            self.num_jobs = threads
        self.atype = atype.split('-')[1]
        self.analysis = analysis
        self.path, self.run_id, self.files, self.demuxed = self.setup_dir(Path(path))

        # Add the split directory to the MetaData object
        self.add_path('analysis{}'.format(self.run_id), '')
        self.columns = []
        self.config = self.read_config_file(config)

    def __del__(self):
        del self.db

    def setup_dir(self, path):
        """ Setup the directory to run the analysis. """
        log('In setup_dir')
        files = {}
        run_id = 0
        new_dir = path / 'analysis{}'.format(run_id)
        while new_dir.is_dir():
            run_id += 1
            new_dir = path / 'analysis{}'.format(run_id)
        new_dir = new_dir.resolve()
        root_files, root_path = self.db.get_mongo_files(self.access_code)
        if self.analysis:
            run('mkdir {}'.format(new_dir), shell=True, check=True)

            if '.fastq.gz' == Path(root_files['reads']).suffix:
                # Create links to the files
                (new_dir / 'barcodes.fastq.gz').symlink_to(root_files['barcodes'])
                (new_dir / 'sequences.fastq.gz').symlink_to(root_files['reads'])

                # Add the links to the files dict for this analysis
                files['barcodes'] = new_dir / 'barcodes.fastq.gz'
                files['reads'] = new_dir / 'sequences.fastq.gz'

                demuxed = False
            elif '.zip' == Path(root_files['reads']).suffix:
                (new_dir / 'data.zip').symlink_to(root_files['reads'])
                files['data'] = new_dir / 'data.zip'
                demuxed = True
            else:
                demuxed = False
                log('Invalid extension')
                log(root_files['reads'])
                # This should be caught when uploading the data

            (new_dir / 'metadata.tsv').symlink_to(root_files['metadata'])
            files['metadata'] = new_dir / 'metadata.tsv'
            log('Run analysis')
        else:
            run_id -= 1
            new_dir = path / 'analysis{}'.format(run_id)
            if (new_dir / 'summary').is_dir():
                rmtree(new_dir / 'summary')
            string_files = root_files['analysis{}'.format(run_id)]
            files = {key: Path(string_files[key]) for key in string_files.keys()}
            log("Loaded files")
            log(files.keys())
            log("Skip analysis")
            demuxed = False

        log("Analysis directory is {}".format(new_dir))
        return new_dir, str(run_id), files, demuxed

    def unzip(self):
        """ Split the libraries and perform quality analysis. """
        self.add_path('reads', '')
        command = 'unzip {} -d {}'.format(self.files['data'],
                                          self.files['reads'])
        self.jobtext.append(command)

    def read_config_file(self, config_file):
        """ Read the provided config file to determine settings for the analysis. """
        config = {}
        # If no config was provided load the default
        if config_file is None:
            log('Using default config')
            with open(STORAGE_DIR / 'config_file.txt', 'r') as f:
                page = f.read()
        else:
            # Otherwise write the file to the analysis directory for future reference
            log('Using custom config: {}'.format(self.path / 'config_file.txt'))
            with open(self.path / 'config_file.txt', 'w+') as f:
                f.write(config_file)
            # And load the file contents
            page = config_file
        # Parse the config
        lines = page.split('\n')
        for line in lines:
            if line.startswith('#') or line == '':
                continue
            else:
                parts = line.split('\t')
                config[parts[0]] = parts[1]

        # Parse the metadata values to be included in the analysis
        if config['metadata'] == 'all':
            # If it's set to all get all the headers from the mapping file
            with open(self.files['mapping']) as f:
                header = f.readline()
            config['metadata'] = header.strip().split('\t')
        else:
            # Otherwise split the values into a list
            config['metadata'] = config['metadata'].split(',')
        # Ensure #SampleID isn't included
        if '#SampleID' in config['metadata']:
            config['metadata'].remove('#SampleID')
        return config

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(files['mapping'], self.path)
        self.jobtext.append(cmd)

    def get_job_params(self):
        params = {
            'walltime': '4:00',
            'walltime2': '2:00',
            'jobname': self.owner + '_' + self.run_id,
            'nodes': self.num_jobs,
            'memory': 1000,
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
        """ Move all visualization files intended for the user to a set location. """
        try:
            log('Move analysis files into directory')
            self.add_path('visualizations_dir', '')
            if not self.files['visualizations_dir'].is_dir():
                self.files['visualizations_dir'].mkdir()
            for key in self.files.keys():
                f = self.files[key]
                if '.qzv' in str(self.files[key]):
                    new_file = f.name
                    copy(self.files[key], self.files['visualizations_dir'] / new_file)
        except FileNotFoundError as e:
            log(e)
            raise AnalysisError(e.args[1])

    def write_file_locations(self):
        """
        Update the relevant document's metadata and
        create a file_index in the analysis directoy.
        """
        string_files = {str(key): str(self.files[key]) for key in self.files.keys()}
        self.db.update_metadata(self.access_code,
                                'analysis{}'.format(self.run_id),
                                string_files)

        # Create the file index
        with open(self.path / 'file_index.tsv', 'w') as f:
            f.write('{}\t{}\n'.format(self.owner, self.access_code))
            f.write('Key\tPath\n')
            for key in self.files:
                f.write('{}\t{}\n'.format(key, self.files[key]))
        log(self.files.keys())

    def add_path(self, name, extension=''):
        """ Add a file or directory with the full path to self.files. """
        self.files[name] = Path('{}{}'.format(self.path / name, extension))

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        fp = self.files['metadata']
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
        self.files['mapping'] = mapping_file


class Qiime1(Tool):
    """ A class for qiime 1.9.1 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing):
        super().__init__(owner, access_code, atype, config, testing)
        if testing:
            self.jobtext.append('source activate qiime1;')
        else:
            self.jobtext.append('module load qiime/1.9.1;')

        settings = [
            'pick_otus:enable_rev_strand_match True',
            'alpha_diversity:metrics shannon,PD_whole_tree,chao1,observed_species'
        ]
        with open(self.path / 'params.txt', 'w') as f:
            f.write('\n'.join(settings))

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(self.files['mapping'], self.path)
        self.jobtext.append(cmd)

    def split_libraries(self):
        """ Split the libraries and perform quality analysis. """
        self.add_path('split_output', '')

        # Run the script
        if self.demuxed:
            cmd = 'multiple_split_libraries_fastq.py -o {} -i {};'
            command = cmd.format(self.files['split_output'],
                                 self.files['reads'])
        else:
            cmd = 'split_libraries_fastq.py -o {} -i {} -b {} -m {};'
            command = cmd.format(self.files['split_output'],
                                 self.files['reads'],
                                 self.files['barcodes'],
                                 self.files['mapping'])
        self.jobtext.append(command)

    def pick_otu(self):
        """ Run the pick OTU scripts. """
        self.add_path('otu_output', '')

        # Run the script
        cmd = 'pick_{}_reference_otus.py -a -O {} -o {} -i {} -p {};'
        command = cmd.format(self.atype,
                             self.num_jobs,
                             self.files['otu_output'],
                             self.files['split_output'] / 'seqs.fna',
                             self.path / 'params.txt')
        self.jobtext.append(command)

    def core_diversity(self):
        """ Run the core diversity analysis script. """
        self.add_path('diversity_output', '')

        # Run the script
        cmd = 'core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {} -c {} -p {};'
        if self.atype == 'open':
            command = cmd.format(self.files['diversity_output'],
                                 self.files['otu_output'] / 'otu_table_mc2_w_tax_no_pynast_failures.biom',
                                 self.files['mapping'],
                                 self.files['otu_output'] / 'rep_set.tre',
                                 self.config['sampling_depth'],
                                 ','.join(self.config['metadata']),
                                 self.path / 'params.txt')
        else:
            command = cmd.format(self.files['diversity_output'],
                                 self.files['otu_output'] / 'otu_table.biom',
                                 self.files['mapping'],
                                 self.files['otu_output'] / '97_otus.tree',
                                 self.config['sampling_depth'],
                                 ','.join(self.config['metadata']),
                                 self.path / 'params.txt')

        self.jobtext.append(command)

    def sanity_check(self):
        """ Check that counts match after split_libraries and pick_otu. """
        try:
            # Count the sequences prior to diversity analysis
            cmd = '{} count_seqs.py -i {}'.format(self.jobtext[0],
                                                  self.files['split_output'] / 'seqs.fna')
            log('Run command: {}'.format(cmd))
            output = run(cmd, shell=True, check=True, stdout=PIPE)
            out = output.stdout.decode('utf-8')
            log('Output: {}'.format(out))
            initial_count = int(out.split('\n')[1].split(' ')[0])

            # Count the sequences in the output of the diversity analysis
            with open(self.files['diversity_output'] / 'biom_table_summary.txt') as f:
                lines = f.readlines()
                log('Check lines: {}'.format(lines))
                final_count = int(lines[2].split(':')[-1].strip().replace(',', ''))

            # Check that the counts are approximately equal
            if abs(initial_count - final_count) > 0.30 * (initial_count + final_count):
                message = 'Large difference ({}) between initial and final counts'
                log('Raise analysis error')
                raise AnalysisError(message.format(initial_count - final_count))
            log('Sanity check completed successfully')

        except ValueError as e:
            log(str(e))
            raise AnalysisError(e.args[0])

    def summarize(self):
        """
        Create summary of analysis results
        """
        log('Run summarize')
        diversity = self.files['diversity_output']
        summary_files = defaultdict(list)

        (self.path / 'summary').mkdir()
        self.add_path('summary', '')

        # Convert and store the otu table
        cmd = '{} biom convert -i {} -o {} --to-tsv --header-key="taxonomy"'
        cmd = cmd.format(self.jobtext[0],
                         self.files['otu_output'] / 'otu_table.biom',
                         self.path / 'otu_table.tsv')
        log(cmd)
        run(cmd, shell=True, check=True)

        # Add the text OTU table to the summary
        copy(self.path / 'otu_table.tsv', self.files['summary'])
        summary_files['otu'].append('otu_table.tsv')

        def move_files(path, catagory):
            """ Collect the contents of all files match the regex in path """
            files = diversity.glob(path.format(depth=self.config['sampling_depth']))
            for data in files:
                copy(data, self.files['summary'])
                summary_files[catagory].append(data.name)

        move_files('biom_table_summary.txt', 'otu')                       # Biom summary
        move_files('arare_max{depth}/alpha_div_collated/*.txt', 'alpha')  # Alpha div
        move_files('bdiv_even{depth}/*.txt', 'beta')                      # Beta div
        move_files('taxa_plots/*.txt', 'taxa')                            # Taxa summary
        # Get the mapping file
        copy(self.files['mapping'], self.path / 'summary/.')
        # Get the template
        copy(STORAGE_DIR / 'revtex.tplx', self.files['summary'])
        log('Summary path')
        log(self.path / 'summary')
        summarize(metadata=self.config['metadata'],
                  analysis_type='qiime1',
                  files=summary_files,
                  execute=True,
                  name='analysis',
                  run_path=self.path / 'summary')
        log('Make archive')
        result = make_archive(self.path / 'summary{}'.format(self.run_id),
                              format='zip',
                              root_dir=self.path,
                              base_dir='summary')
        log(result)
        log('Summary completed successfully')
        return self.path / 'summary/analysis.pdf'

    def run_analysis(self):
        """ Perform some analysis. """
        self.create_qiime_mapping_file()
        self.validate_mapping()
        if self.demuxed:
            self.unzip()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
        jobfile = self.path / (self.run_id + '_job')
        self.add_path(jobfile, '.lsf')
        error_log = self.path / self.run_id
        self.add_path(error_log, '.err')
        if self.testing:
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
            try:
                self.run_analysis()
            except CalledProcessError as e:
                raise AnalysisError(e.args[0])
        self.sanity_check()
        summary = self.summarize()
        self.move_user_files()
        self.write_file_locations()
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

    def __init__(self, owner, access_code, atype, config, testing):
        super().__init__(owner, access_code, atype, config, testing)
        if testing:
            self.jobtext.append('source activate qiime2;')
        else:
            self.jobtext.append('module load qiime2/2018.4;')

    # ======================= #
    # # # Qiime2 Commands # # #
    # ======================= #
    def qimport(self, itype='EMPSingleEndSequences'):
        """ Split the libraries and perform quality analysis. """

        self.files['demux_file'] = self.path / 'qiime_artifact.qza'
        # Create a directory to import as a Qiime2 object
        if self.demuxed:
            cmd = [
                'qiime tools import ',
                '--type {} '.format('"SampleData[PairedEndSequencesWithQuality]"'),
                '--input-path {}'.format(self.files['reads']),
                '--source-format {}'.format('CasavaOneEightSingleLanePerSampleDirFmt'),
                '--output-path {};'.format(self.files['demux_file'])
            ]
            self.jobtext.append(' '.join(cmd))
        else:
            self.files['working_dir'] = self.path / 'import_dir'
            if not self.files['working_dir'].is_dir():
                self.files['working_dir'].mkdir()

            # Create links to the data in the qiime2 import directory
            (self.files['working_dir'] /
             'barcodes.fastq.gz').symlink_to(self.path /
                                             'barcodes.fastq.gz')
            (self.files['working_dir'] /
             'sequences.fastq.gz').symlink_to(self.path /
                                              'sequences.fastq.gz')

            # Run the script
            cmd = 'qiime tools import --type {} --input-path {} --output-path {};'
            command = cmd.format(itype, self.files['working_dir'], self.files['working_file'])
            self.jobtext.append(command)

    def demultiplex(self):
        """ Demultiplex the reads. """
        # Add the otu directory to the MetaData object
        self.add_path('demux_file', '.qza')

        # Run the script
        cmd = [
            'qiime demux emp-single',
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

    def core_diversity(self, p_sampling_depth=1109):
        """ Run core diversity """
        self.add_path('core_metrics_results', '')
        cmd = [
            'qiime diversity core-metrics-phylogenetic',
            '--i-phylogeny {}'.format(self.files['rooted_tree']),
            '--i-table {}'.format(self.files['table_{}'.format(self.atype)]),
            '--p-sampling-depth {}'.format(p_sampling_depth),
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
        cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                self.files['demux_viz'],
                                                                self.path / 'temp')
        run(cmd, shell=True, check=True)

        df = read_csv(self.path / 'temp' / 'per-sample-fastq-counts.csv', sep=',', header=0)
        initial_count = sum(df['Sequence count'])
        rmtree(self.path / 'temp')

        # Check the counts after DADA2/DeBlur
        cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                self.files['table_{}'.format(self.atype)],
                                                                self.path / 'temp')
        run(cmd, shell=True, check=True)
        log(cmd)

        cmd = '{} biom summarize-table -i {}'.format(self.jobtext[0], self.path / 'temp' / 'feature-table.biom')
        result = run(cmd, stdout=PIPE, stderr=PIPE, shell=True)
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
        self.create_qiime_mapping_file()

        if self.demuxed:
            self.unzip()
        self.qimport()
        if not self.demuxed:
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
        log(self.jobtext)

    def run(self):
        """ Perform some analysis. """
        try:
            if self.analysis:
                self.setup_analysis()
                jobfile = self.path / (self.run_id + '_job')
                self.add_path(jobfile, 'lsf')
                error_log = self.path / self.run_id
                self.add_path(error_log, 'err')
                if self.testing:
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
            self.write_file_locations()
            summary = self.summarize()
            log('Send email')
            send_email(doc.email,
                       doc.owner,
                       'analysis',
                       analysis_type='Qiime2 (2018.4) ' + self.atype,
                       study_name=doc.study,
                       summary=summary,
                       testing=self.testing)
        except CalledProcessError as e:
            raise AnalysisError(e.args[0])

    def summarize(self):
        """ Create summary of the files produced by the qiime2 analysis. """
        log('Start Qiime2 summary')

        # Setup the summary directory
        summary_files = defaultdict(list)
        self.add_path('summary')
        if not (self.path / 'summary').is_dir():
            (self.path / 'summary').mkdir()

        # Get Taxa
        cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                self.files['taxa_bar_plot'],
                                                                self.path / 'temp')
        run(cmd, shell=True, check=True)
        taxa_files = (self.path / 'temp').glob('level*.csv')
        for taxa_file in taxa_files:
            copy(taxa_file, self.files['summary'])
            summary_files['taxa'].append(taxa_file.name)
        rmtree(self.path / 'temp')

        # Get Beta
        beta_files = self.files['core_metrics_results'].glob('*pcoa*')
        for beta_file in beta_files:
            cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                    beta_file,
                                                                    self.path / 'temp')
            run(cmd, shell=True, check=True)
            dest_file = self.files['summary'] / (beta_file.name.split('.')[0] + '.txt')
            copy(self.path / 'temp' / 'ordination.txt', dest_file)
            log(dest_file)
            summary_files['beta'].append(dest_file.name)
            rmtree(self.path / 'temp')

        # Get Alpha
        for metric in ['shannon', 'faith_pd', 'observed_otus']:
            cmd = '{} qiime tools export {} --output-dir {}'.format(self.jobtext[0],
                                                                    self.files['alpha_rarefaction'],
                                                                    self.path / 'temp')
            run(cmd, shell=True, check=True)

            metric_file = self.path / 'temp/{}.csv'.format(metric)
            copy(metric_file, self.files['summary'])
            summary_files['alpha'].append(metric_file.name)
            rmtree(self.path / 'temp')

        # Get the mapping file
        copy(self.files['mapping'], self.files['summary'])
        # Get the template
        copy(STORAGE_DIR / 'revtex.tplx', self.files['summary'])

        log('Summary path')
        log(self.path / 'summary')
        summarize(metadata=self.config['metadata'],
                  analysis_type='qiime2',
                  files=summary_files,
                  execute=True,
                  name='analysis',
                  run_path=self.path / 'summary')

        # Create a zip of the summary
        result = make_archive(self.path / 'summary{}'.format(self.run_id),
                              format='zip',
                              root_dir=self.path,
                              base_dir='summary')
        log('Create archive of summary')
        log(result)

        log('Summary completed succesfully')
        return self.path / 'summary' / 'analysis.pdf'


def run_analysis(qiime):
    """ Run qiime analysis. """
    try:
        qiime.run()
    except AnalysisError as e:
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


def spawn_analysis(atype, user, access_code, config, testing):
    """ Start running the analysis in a new process """
    if 'qiime1' in atype:
        qiime = Qiime1(user, access_code, atype, config, testing)
        p = Process(target=run_analysis, args=(qiime,))
    elif 'qiime2' in atype:
        qiime = Qiime2(user, access_code, atype, config, testing)
        p = Process(target=run_analysis, args=(qiime,))
    elif 'test' in atype:
        time = float(atype.split('-')[-1])
        p = Process(target=test, args=(time, atype))
    p.start()
    return p
