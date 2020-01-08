from subprocess import run

from mmeds.config import DATABASE_DIR
from mmeds.util import setup_environment
from mmeds.error import AnalysisError
from mmeds.tool import Tool
from mmeds.log import MMEDSLog

logger = MMEDSLog('debug').logger


class Qiime1(Tool):
    """ A class for qiime 1.9.1 analysis of uploaded studies. """

    def __init__(self, owner, access_code, tool_type, analysis_type, config, testing,
                 analysis=True, restart_stage=0, child=False, kill_stage=-1):
        super().__init__(owner, access_code, tool_type, analysis_type, config, testing,
                         analysis=analysis, restart_stage=restart_stage, child=child)
        load = 'module use {}/.modules/modulefiles; module load qiime/1.9.1;'.format(DATABASE_DIR.parent)
        print('initialzing Qiime1')
        print('I am a child? {}'.format(child))
        self.jobtext.append(load)
        self.module = load
        if testing:
            settings = [
                'alpha_diversity:metrics	shannon',
                'beta_diversity_through_plots:ignore_missing_samples	True'
            ]
        else:
            settings = [
                'pick_otus:enable_rev_strand_match	True',
                'alpha_diversity:metrics	shannon,PD_whole_tree,chao1,observed_species',
                'beta_diversity_through_plots:ignore_missing_samples	True'
            ]
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))

        with open(self.path / 'params.txt', 'w') as f:
            f.write('\n'.join(settings))
        self.add_path('params', '.txt')

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(self.get_file('mapping'),
                                                                self.run_dir)
        self.jobtext.append(cmd)

    def join_paired_ends(self):
        """ Join forward and reverse reads into a single file. """
        self.add_path('joined_dir', '')
        cmd = 'join_paired_ends.py -f {} -r {} --output_dir {}'
        self.jobtext.append(cmd.format(self.get_file('for_reads'),
                                       self.get_file('rev_reads'),
                                       self.get_file('joined_dir')))

    def zip_joined_reads(self):
        """ Zip the output fastq created by joining the reads. """
        self.add_path('joined_reads', '.fastq.gz')
        cmd = 'gzip {}'.format(self.get_file('joined_dir') / 'fastqjoin.join.fastq')
        self.jobtext.append(cmd)
        cmd = 'ln -s {} {}'.format(self.get_file('joined_dir') / 'fastqjoin.join.fastq.gz',
                                   self.get_file('joined_reads'))
        self.jobtext.append(cmd)

    def split_libraries(self):
        """ Split the libraries and perform quality analysis. """
        self.add_path('split_output', '')

        # Run the script
        if 'demuxed' in self.doc.reads_type:
            cmd = 'multiple_split_libraries_fastq.py -o {} -i {};'
            command = cmd.format(self.get_file('split_output'),
                                 self.get_file('for_reads'))
        elif 'single' in self.doc.reads_type:
            cmd = 'split_libraries_fastq.py -o {} -i {} -b {} -m {} --barcode_type {};'
            command = cmd.format(self.get_file('split_output'),
                                 self.get_file('for_reads'),
                                 self.get_file('barcodes'),
                                 self.get_file('mapping'),
                                 12)
        elif 'paired' in self.doc.reads_type:
            cmd = 'split_libraries_fastq.py -o {} -i {} -b {} -m {} --barcode_type {} --rev_comp_mapping_barcodes;'
            command = cmd.format(self.get_file('split_output'),
                                 self.get_file('joined_dir') / 'fastqjoin.join.fastq',
                                 self.get_file('barcodes'),
                                 self.get_file('mapping'),
                                 12)
        self.jobtext.append(command)

    def pick_otu(self):
        """ Run the pick OTU scripts. """
        self.add_path('otu_output', '')
        # Link files for the otu and biom tables
        if 'closed' == self.doc.analysis_type:
            self.add_path(self.get_file('otu_output').name + '/97_otus', '.tree', key='otu_table')
            self.add_path(self.get_file('otu_output').name + '/otu_table', '.biom', key='biom_table')
        elif 'open' == self.doc.analysis_type:
            self.add_path(self.get_file('otu_output').name + '/rep_set', '.tre', key='otu_table')
            self.add_path(self.get_file('otu_output').name + '/otu_table_mc2_w_tax_no_pynast_failures',
                          '.biom', key='biom_table')

        cmd = 'pick_{}_reference_otus.py -a -O {} -o {} -i {} -p {};'
        command = cmd.format(self.doc.analysis_type,
                             self.num_jobs,
                             self.get_file('otu_output'),
                             self.get_file('split_output') / 'seqs.fna',
                             self.get_file('params'))
        self.jobtext.append(command)

    def split_otu(self):
        """ Split the otu table by column values. """
        for column in self.doc.config['sub_analysis']:
            self.add_path('split_otu_{}'.format(column))
            cmd = 'split_otu_table.py -i {} -m {} -f {} -o {} --suppress_mapping_file_output;'
            command = cmd.format(self.get_file('biom_table'),
                                 self.get_file('mapping'),
                                 column,
                                 self.get_file('split_otu_{}'.format(column)))
            self.jobtext.append(command)

    def core_diversity(self):
        """ Run the core diversity analysis script. """
        self.add_path('diversity_output', '')

        cmd = 'core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {} -p {} -c {} -O {} -a;'
        command = cmd.format(self.get_file('diversity_output'),
                             self.get_file('biom_table'),
                             self.get_file('mapping'),
                             self.get_file('otu_table'),
                             self.doc.config['sampling_depth'],
                             self.path / 'params.txt',
                             ','.join(self.doc.config['metadata']),
                             self.num_jobs)
        self.jobtext.append(command)

    def sanity_check(self):
        """ Check that counts match after split_libraries and pick_otu. """
        try:
            # Count the sequences prior to diversity analysis
            new_env = setup_environment('qiime/1.9.1')
            cmd = ['count_seqs.py', '-i', str(self.get_file('split_output', True) / 'seqs.fna')]
            output = run(cmd, check=True, env=new_env)

            out = output.stdout.decode('utf-8')
            logger.debug('Output: {}'.format(out))
            initial_count = int(out.split('\n')[1].split(' ')[0])

            # Count the sequences in the output of the diversity analysis
            with open(self.get_file('diversity_output', True) / 'biom_table_summary.txt') as f:
                lines = f.readlines()
                logger.debug('Check lines: {}'.format(lines))
                final_count = int(lines[2].split(':')[-1].strip().replace(',', ''))

            # Check that the counts are approximately equal
            if abs(initial_count - final_count) > 0.30 * (initial_count + final_count):
                message = 'Large difference ({}) between initial and final counts'
                logger.debug('Raise analysis error')
                raise AnalysisError(message.format(initial_count - final_count))
            logger.debug('Sanity check completed successfully')

        except ValueError as e:
            logger.debug(str(e))
            raise AnalysisError(e.args[0])

    def setup_analysis(self):
        """ Add all the necessary commands to the jobfile """
        # Only the child run this analysis
        if not self.doc.sub_analysis:
            self.validate_mapping()
            if 'demuxed' in self.doc.reads_type:
                self.unzip()
            elif 'paired' in self.doc.reads_type:
                self.join_paired_ends()
            self.split_libraries()
            self.pick_otu()
            if not self.doc.config['sub_analysis'] == 'None':
                self.split_otu()
        self.core_diversity()
        self.write_file_locations()

        # Perform standard tool setup
        super().setup_analysis()
