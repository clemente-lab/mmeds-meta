from subprocess import run, CalledProcessError
from pathlib import Path

from mmeds.config import JOB_TEMPLATE
from mmeds.mmeds import send_email, log, setup_environment
from mmeds.error import AnalysisError
from mmeds.tool import Tool


class Qiime1(Tool):
    """ A class for qiime 1.9.1 analysis of uploaded studies. """

    def __init__(self, owner, access_code, atype, config, testing):
        super().__init__(owner, access_code, atype, config, testing)
        if testing:
            self.jobtext.append('module use ~/.modules/modulefiles; module load qiime1;')
            settings = [
                'alpha_diversity:metrics	shannon'
            ]
        else:
            self.jobtext.append('module use $MMEDS/.modules/modulefiles; module load qiime1;')
            settings = [
                'pick_otus:enable_rev_strand_match	True',
                'alpha_diversity:metrics	shannon,PD_whole_tree,chao1,observed_species'
            ]
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))

        with open(self.path / 'params.txt', 'w') as f:
            f.write('\n'.join(settings))

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
        if 'demuxed' in self.data_type:
            cmd = 'multiple_split_libraries_fastq.py -o {} -i {};'
            command = cmd.format(self.get_file('split_output'),
                                 self.get_file('for_reads'))
        elif self.data_type == 'single_end':
            cmd = 'split_libraries_fastq.py -o {} -i {} -b {} -m {} --barcode_type {};'
            command = cmd.format(self.get_file('split_output'),
                                 self.get_file('for_reads'),
                                 self.get_file('barcodes'),
                                 self.get_file('mapping'),
                                 12)
        elif self.data_type == 'paired_end':
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

        # Run the script
        cmd = 'pick_{}_reference_otus.py -a -O {} -o {} -i {} -p {};'
        command = cmd.format(self.atype,
                             self.num_jobs,
                             self.get_file('otu_output'),
                             self.get_file('split_output') / 'seqs.fna',
                             self.run_dir / 'params.txt')
        self.jobtext.append(command)

    def core_diversity(self):
        """ Run the core diversity analysis script. """
        self.add_path('diversity_output', '')

        # Run the script
        cmd = 'core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {} -p {};'
        if self.atype == 'open':
            command = cmd.format(self.get_file('diversity_output'),
                                 self.get_file('otu_output') / 'otu_table_mc2_w_tax_no_pynast_failures.biom',
                                 self.get_file('mapping'),
                                 self.get_file('otu_output') / 'rep_set.tre',
                                 self.config['sampling_depth'],
                                 self.path / 'params.txt')
        else:
            command = cmd.format(self.get_file('diversity_output'),
                                 self.get_file('otu_output') / 'otu_table.biom',
                                 self.get_file('mapping'),
                                 self.get_file('otu_output') / '97_otus.tree',
                                 self.config['sampling_depth'],
                                 self.path / 'params.txt')
        if not self.testing:
            command = command.strip(';') + ' -c {};'.format(','.join(self.config['metadata']))

        self.jobtext.append(command)

    def sanity_check(self):
        """ Check that counts match after split_libraries and pick_otu. """
        try:
            # Count the sequences prior to diversity analysis
            new_env = setup_environment('qiime1')
            script_path = Path(new_env['PATH'].split(':')[0])
            cmd = ['python', str(script_path / 'count_seqs.py'), '-i', str(self.files['split_output'] / 'seqs.fna')]
            output = run(cmd, check=True, env=new_env)

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

    def setup_analysis(self):
        """ Add all the necessary commands to the jobfile """
        self.validate_mapping()
        if 'demuxed' in self.data_type:
            self.unzip()
        if 'paired' in self.data_type:
            self.join_paired_ends()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
        self.summary()
        self.write_file_locations()

    def run_analysis(self):
        """ Perform some analysis. """
        self.setup_analysis()
        self.add_path(self.run_id + '_job', '.lsf', 'jobfile')
        self.add_path('err' + self.run_id, '.err', 'errorlog')
        jobfile = self.files['jobfile']
        log(jobfile)
        error_log = self.files['errorlog']
        log(error_log)
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
            # Submit the job

            #  Temporary for testing on Minerva
            run([jobfile], check=True)
            #  job_id = int(str(output.stdout).split(' ')[1].strip('<>'))
            #  self.wait_on_job(job_id)

    def run(self):
        """ Execute all the necessary actions. """
        try:
            if self.analysis:
                self.run_analysis()
            self.sanity_check()
            self.move_user_files()
            doc = self.db.get_metadata(self.access_code)
            if not self.testing:
                send_email(doc.email,
                           doc.owner,
                           'analysis',
                           analysis_type='Qiime1',
                           study_name=doc.study,
                           testing=self.testing,
                           summary=self.path / 'summary/analysis.pdf')
        except CalledProcessError as e:
            self.move_user_files()
            self.write_file_locations()
            raise AnalysisError(e.args[0])
