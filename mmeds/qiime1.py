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

    def summary(self):
        """ Setup script to create summary. """
        self.add_path('summary')
        if not (self.path / 'summary').is_dir():
            (self.path / 'summary').mkdir()

        self.jobtext.append('source deactivate;')
        self.jobtext.append('source activate mmeds-stable;')
        cmd = [
            'summarize.py ',
            '--path {}'.format(self.path),
            '--tool_type qiime1',
            '--metadata {}'.format(','.join(self.config['metadata'])),
            '--sampling_depth {}'.format(self.config['sampling_depth']),
            '--load_info "{}";'.format(self.jobtext[0])
        ]
        self.jobtext.append(' '.join(cmd))

    def run_analysis(self):
        """ Perform some analysis. """
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
        self.summary()
        self.write_file_locations()
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
        try:
            if self.analysis:
                self.run_analysis()
            self.sanity_check()
            self.move_user_files()
            doc = self.db.get_metadata(self.access_code)
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
