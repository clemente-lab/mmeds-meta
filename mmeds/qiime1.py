from subprocess import run, CalledProcessError, PIPE

from mmeds.config import JOB_TEMPLATE
from mmeds.mmeds import send_email, log
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
            cmd = 'split_libraries_fastq.py -o {} -i {} -b {} -m {} --barcode_type {};'
            command = cmd.format(self.files['split_output'],
                                 self.files['reads'],
                                 self.files['barcodes'],
                                 self.files['mapping'],
                                 12)
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
        cmd = 'core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {} -p {};'
        if self.atype == 'open':
            command = cmd.format(self.files['diversity_output'],
                                 self.files['otu_output'] / 'otu_table_mc2_w_tax_no_pynast_failures.biom',
                                 self.files['mapping'],
                                 self.files['otu_output'] / 'rep_set.tre',
                                 self.config['sampling_depth'],
                                 self.path / 'params.txt')
        else:
            command = cmd.format(self.files['diversity_output'],
                                 self.files['otu_output'] / 'otu_table.biom',
                                 self.files['mapping'],
                                 self.files['otu_output'] / '97_otus.tree',
                                 self.config['sampling_depth'],
                                 self.path / 'params.txt')
        if not self.testing:
            command = command.strip(';') + ' -c {};'.format(','.join(self.config['metadata']))

        self.jobtext.append(command)

    def sanity_check(self):
        """ Check that counts match after split_libraries and pick_otu. """
        try:
            # Count the sequences prior to diversity analysis
            cmd = '{} count_seqs.py -i {}'.format(self.jobtext[0],
                                                  self.files['split_output'] / 'seqs.fna')
            output = run('bash -c "{}"'.format(cmd), shell=True, check=True, stdout=PIPE)
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
        if self.demuxed:
            self.unzip()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
        self.summary()
        self.write_file_locations()

    def run_analysis(self):
        """ Perform some analysis. """
        self.setup_analysis()
        jobfile = self.path / (self.run_id + '_job')
        self.add_path(jobfile, '.lsf')
        error_log = self.path / self.run_id
        self.add_path(error_log, '.err')
        if self.testing:
            # Open the jobfile to write all the commands
            with open(str(jobfile) + '.lsf', 'w') as f:
                f.write('#!/bin/bash -l\n')
                f.write('\n'.join(self.jobtext))
            # Run the command
            run('bash -c "bash {}.lsf"'.format(jobfile), shell=True, check=True)
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
            #  Temporary for testing on Minerva
            #  FIXME
            #  output = run('bsub < {}.lsf'.format(jobfile), stdout=PIPE, shell=True, check=True)
            run('sh {}.lsf'.format(jobfile), stdout=PIPE, shell=True, check=True)
            #  job_id = int(str(output.stdout).split(' ')[1].strip('<>'))
            #  self.wait_on_job(job_id)

    def run(self):
        """ Execute all the necessary actions. """
        try:
            if self.analysis:
                self.run_analysis()
            self.sanity_check()
            self.move_user_files()
            self.write_file_locations()
            self.summary()
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
