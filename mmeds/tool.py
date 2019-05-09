from pathlib import Path
from subprocess import run, CalledProcessError
from shutil import copy
from time import sleep
from copy import copy as classcopy
from copy import deepcopy

from mmeds.database import Database
from mmeds.util import (log, create_qiime_from_mmeds, test_log,
                        load_metadata, write_metadata, camel_case,
                        send_email)
from mmeds.error import AnalysisError
from mmeds.config import COL_TO_TABLE, JOB_TEMPLATE

import multiprocessing as mp


class Tool(mp.Process):
    """
    The base class for tools used by mmeds inherits the python Process class.
    self.run is overridden by the classes that inherit from Tool so the analysis
    will happen in seperate processes.
    """

    def __init__(self, owner, access_code, atype, config, testing, threads=10, analysis=True, child=False):
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
        :child: A boolean. If True this Tool object is the child of another tool.
        """
        super().__init__()
        self.study_code = access_code
        self.testing = testing
        self.jobtext = []
        self.owner = owner
        self.atype = atype.split('-')[1]
        self.tool = atype.split('-')[0]
        self.analysis = analysis
        self.config = config
        self.columns = []

        with Database(owner=self.owner, testing=self.testing) as db:
            metadata = db.get_metadata(self.study_code)
            self.doc = metadata.generate_AnalysisDoc(self.name, atype)

        log('initial doc.files')
        self.path = Path(self.doc.path)

        if testing:
            self.num_jobs = 2
        else:
            self.num_jobs = min([threads, mp.cpu_count()])

        self.run_dir = Path('$RUN_{}'.format(self.doc.name))
        self.add_path(self.path, key='path')
        self.write_config()
        self.create_qiime_mapping_file()
        self.children = []
        self.is_child = False
        self.data_type = self.doc.data_type
        self.doc.save()

    def add_path(self, name, extension='', key=None):
        """ Add a file or directory with the full path to self.doc. """
        if key:
            self.doc.files[str(key)] = '{}{}'.format(self.path / name, extension)
        else:
            self.doc.files[str(name)] = '{}{}'.format(self.path / name, extension)
        self.doc.save()

    def get_file(self, key, absolute=False):
        """ Get the path to the file stored under 'key' relative to the run dir """
        if absolute:
            file_path = Path(self.doc.files[key])
        else:
            file_path = self.run_dir / Path(self.doc.files[key]).relative_to(self.path)
        return file_path

    def write_config(self):
        """ Write out the config file being used to the working directory. """
        config_text = []
        for (key, value) in self.config.items():
            # Don't write values that are generated on loading
            if key in ['Together', 'Separate', 'metadata_continuous', 'taxa_levels_all', 'metadata_all',
                       'sub_analysis_continuous', 'sub_analysis_all']:
                continue
            # If the value was initially 'all', write that
            elif key in ['taxa_levels', 'metadata', 'sub_analysis']:
                if self.config['{}_all'.format(key)]:
                    config_text.append('{}\t{}'.format(key, 'all'))
                # Write lists as comma seperated strings
                elif value:
                    config_text.append('{}\t{}'.format(key, ','.join(list(map(str, value)))))
                else:
                    config_text.append('{}\t{}'.format(key, 'none'))
            else:
                config_text.append('{}\t{}'.format(key, value))
        (self.path / 'config_file.txt').write_text('\n'.join(config_text))
        log('{} write metadata {}'.format(self.name, self.config['metadata']), True)

    def unzip(self):
        """ Split the libraries and perform quality analysis. """
        self.add_path('for_reads', '')
        command = 'unzip {} -d {}'.format(self.get_file('data'),
                                          self.get_file('for_reads'))
        self.jobtext.append(command)

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(self.get_file('mapping', True), self.path)
        self.jobtext.append(cmd)

    def get_job_params(self):
        params = {
            'walltime': '6:00',
            'walltime2': '2:00',
            'jobname': '{}-{}'.format(self.owner, self.doc.name),
            'path': self.path,
            'nodes': self.num_jobs,
            'memory': 1000,
            'queue': 'premium'
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
            output = run(['/hpc/lsf/9.1/linux2.6-glibc2.3-x86_64/bin/bjobs'],
                         capture_output=True).stdout.decode('utf-8').split('\n')
            for job in output:
                # If the job is found set it back to true
                if str(job_id) in job:
                    running = True
            # Wait thirty seconds to check again
            sleep(30)

    def move_user_files(self):
        """ Move all visualization files intended for the user to a set location. """
        try:
            log('Move analysis files into directory')
            self.add_path('visualizations_dir', '')
            if not self.get_file('visualizations_dir', True).is_dir():
                self.get_file('visualizations_dir', True).mkdir()
            for key in self.doc.files.keys():
                f = self.get_file(key)
                if '.qzv' in str(self.get_file(key, True)):
                    new_file = f.name
                    copy(self.get_file(key, True), self.get_file('visualizations_dir', True) / new_file)
        except FileNotFoundError as e:
            log(e)
            raise AnalysisError(e.args[1])

    def write_file_locations(self):
        """
        Update the relevant document's metadata and
        create a file_index in the analysis directoy.
        """
        with Database(owner=self.owner, testing=self.testing) as db:
            db.update_metadata(self.study_code, self.doc.name, self.doc.files)

        # Create the file index
        with open(self.path / 'file_index.tsv', 'w') as f:
            f.write('{}\t{}\n'.format(self.owner, self.study_code))
            f.write('Key\tPath\n')
            for key, value in self.doc.files.items():
                f.write('{}\t{}\n'.format(key, value))

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        mmeds_file = self.get_file('metadata', True)

        # Create the Qiime mapping file
        qiime_file = self.path / 'qiime_mapping_file.tsv'

        self.columns = create_qiime_from_mmeds(mmeds_file, qiime_file, self.tool)

        # Add the mapping file to the MetaData object
        self.add_path(qiime_file, key='mapping')

    def summary(self):
        """ Setup script to create summary. """
        self.add_path('summary')
        self.jobtext.append(self.jobtext[0].replace('load', 'unload'))
        self.jobtext.append('module load mmeds-stable;')
        cmd = [
            'summarize.py ',
            '--path "{}"'.format(self.run_dir),
            '--tool_type {}'.format(self.tool)
        ]
        self.jobtext.append(' '.join(cmd))

    def add_summary_files(self):
        """ Add the analysis summary and associated directory to the metadata files """
        with Database(owner=self.owner, testing=self.testing) as db:
            db.update_metadata(self.study_code,
                               '{}_summary'.format(self.doc.name),
                               str(self.path / 'summary/analysis.pdf'))
            db.update_metadata(self.study_code,
                               '{}_summary_dir'.format(self.doc.name),
                               str(self.path / 'summary'))

    def create_child(self, category, value):
        """
        Create a child analysis process using only samples that have a particular value
        in a particular metadata column. Handles creating the analysis directory and such
        ===============================
        :category: The column of the metadata to filter by
        :value: The value that :column: must match for a sample to be included
        """

        child = classcopy(self)
        file_value = camel_case(value)

        # Update process name and children
        child.name = child.name + '-{}-{}'.format(category[1], file_value)
        child.children = []

        child.path = self.path / '{}_{}'.format(category[1], file_value)
        child.path.mkdir()
        child.files = {
            'metadata': child.path / 'metadata.tsv',
        }
        child.doc = self.doc.create_copy(category, value)

        # Link to the parent's OTU table(s)
        for parent_file in ['otu_table', 'biom_table', 'rep_seqs_table', 'stats_table', 'params']:
            if self.doc.get(parent_file) is not None:
                # Add qiime1 specific biom tables
                if 'Qiime1' in self.name and parent_file == 'biom_table':
                    child_file = child.path / 'otu_table.biom'
                    child_file.symlink_to(self.doc.get('split_otu_{}'.format(category[1])) /
                                          'otu_table__{}_{}__.biom'.format(category[1], value))
                    child.set_file(child_file, key='biom_table')
                else:
                    child_file = child.path / self.doc.get(parent_file).name
                    child_file.symlink_to(self.doc.get(parent_file))
                    child.add_path(child_file, key=parent_file)
                    if 'Qiime1' in self.name:
                        child.add_path(self.doc.get('split_otu_{}'.format(category[1])) /
                                       'otu_table__{}_{}__.biom'.format(category[1], value),
                                       key='parent_table')
        else:
            child.add_path(self.path / self.doc.get('otu_table'), key='parent_table')

        # Filter the metadata and write the new file to the childs directory
        mdf = load_metadata(self.get_file('metadata', True))
        new_mdf = mdf.loc[mdf[category] == value]
        write_metadata(new_mdf, child.get_file('metadata', True))

        # Update child's vars
        child.add_path('{}/{}_{}/'.format(child.doc.name, category[1], file_value), '')
        child.run_dir = Path('$RUN_{}_{}_{}'.format(child.doc.name, category[1], file_value))

        # Update the text for the job file
        child.jobtext = deepcopy(self.jobtext)[:2]
        del child.jobtext[-1]
        child.jobtext.append('{}={};'.format(str(child.run_dir).replace('$', ''), child.path))

        # Create a new mapping file
        child.create_qiime_mapping_file()

        # Filter the config for the metadata category selected for this sub-analysis
        child.config = deepcopy(self.config)
        child.config['metadata'] = [cat for cat in self.config['metadata'] if not cat == category[1]]
        child.config['sub_analysis'] = False
        child.is_child = True
        child.write_config()

        # Set the parent pid
        child._parent_pid = self.pid
        return child

    def create_children(self):
        """ Create child analysis processes """
        mdf = load_metadata(self.get_file('metadata', True))

        # For each column selected...
        for col in self.config['sub_analysis']:
            try:
                t_col = (COL_TO_TABLE[col], col)
            # Additional columns won't be in this table
            except KeyError:
                t_col = ('AdditionalMetaData', col)
            # For each value in the column, create a sub-analysis
            for val, df in mdf.groupby(t_col):
                child = self.create_child(t_col, val)
                self.children.append(child)

    def start_children(self):
        """ Start running the child processes. Limiting the concurrent processes to self.num_jobs """
        for child in self.children:
            child.start()

    def wait_on_children(self):
        """ Wait for all child analyses """
        for child in self.children:
            child.join()

    def setup_analysis(self):
        """ Create the summary of the analysis """
        self.summary()

        # Define the job and error files
        jobfile = self.path / 'jobfile.lsf'
        self.add_path(jobfile, key='jobfile')
        submitfile = self.path / 'submitfile'
        self.add_path(submitfile, '.sh', 'submitfile')
        error_log = self.path / 'errorlog'
        self.add_path(error_log, '.err', 'errorlog')
        if self.testing:
            # Open the jobfile to write all the commands
            jobfile.write_text('\n'.join(['#!/bin/bash -l'] + self.jobtext))
            # Set execute permissions
            jobfile.chmod(0o770)
        else:
            log('In run_analysis')
            # Get the job header text from the template
            temp = JOB_TEMPLATE.read_text()
            # Write all the commands
            jobfile.write_text('\n'.join([temp.format(**self.get_job_params())] + self.jobtext))

    def run_analysis(self):
        """ Perform some analysis. """
        try:
            self.setup_analysis()
            if self.is_child:
                # Wait for the otu table to show up
                while not self.get_file('parent_table', True).exists():
                    sleep(10)
            jobfile = self.get_file('jobfile', True)
            self.write_file_locations()
            # Start the sub analyses if so configured
            if self.config['sub_analysis']:
                self.create_children()
                self.start_children()

            if self.testing:
                test_log('{} start job'.format(self.name))
                # Send the output to the error log
                with open(self.get_file('errorlog', True), 'w') as f:
                    # Run the command
                    run([jobfile], stdout=f, stderr=f, check=True)
                test_log('{} finished job'.format(self.name))
            else:
                # Create a file to execute the submission
                submitfile = self.get_file('submitfile', True)
                submitfile.write_text('\n'.join(['#!/bin/bash -l', 'bsub < {};'.format(jobfile)]))
                # Set execute permissions
                submitfile.chmod(0o770)
                jobfile.chmod(0o770)
                #  Temporary for testing on Minerva
                output = run([jobfile], check=True, capture_output=True)
                job_id = int(str(output.stdout).split(' ')[1].strip('<>'))
                self.wait_on_job(job_id)
            with Database(owner=self.owner, testing=self.testing) as db:
                doc = db.get_metadata(self.study_code)
            self.move_user_files()
            self.add_summary_files()
            log('Send email')
            if not self.testing:
                send_email(doc.email,
                           doc.owner,
                           'analysis',
                           analysis_type=self.name + self.atype,
                           study_name=doc.study,
                           testing=self.testing)
        except CalledProcessError as e:
            self.move_user_files()
            self.write_file_locations()
            raise AnalysisError(e.args[0])

    def run(self):
        """ Overrides Process.run() """

        if self.analysis:
            self.run_analysis()
        else:
            self.setup_analysis()
