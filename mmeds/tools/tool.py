from pathlib import Path
from subprocess import run, CalledProcessError
from shutil import copy, rmtree
from time import sleep
from copy import copy as classcopy
from copy import deepcopy
from ppretty import ppretty
from collections import defaultdict
from datetime import datetime

from mmeds.database.database import Database
from mmeds.util import (create_qiime_from_mmeds, write_config,
                        load_metadata, write_metadata, camel_case)
from mmeds.error import AnalysisError, MissingFileError
from mmeds.config import COL_TO_TABLE, JOB_TEMPLATE, DATABASE_DIR
from mmeds.logging import Logger

import multiprocessing as mp

import os


class Tool(mp.Process):
    """
    The base class for tools used by mmeds inherits the python Process class.
    Process.run is overridden by the classes that inherit from Tool so the analysis
    will happen in seperate processes when Process.start() is called.
    """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing,
                 run_on_node, threads=10, analysis=True, child=False, restart_stage=0, kill_stage=-1):
        """
        Setup the Tool class
        ====================
        :owner: A string. The owner of the files being analyzed.
        :parent_code: A string. The code for accessing the files belonging to the parent of this analysis.
        :atype: A string. The type of analysis to perform. Qiime1 or 2, DADA2 or DeBlur.
        :config: A file object. A custom config file, may be None.
        :testing: A boolean. If True run with configurations for a local server.
        :threads: An int. The number of threads to use during analysis, is overwritten if testing==True.
        :analysis: A boolean. If True run a new analysis, if false just summarize the previous analysis.
        :child: A boolean. If True this Tool object is the child of another tool.
        :access_code: A string. If this analysis is being restarted from a previous analysis then this
            will be the access_code for the previous document
        """
        super().__init__()
        self.queue = queue
        self.logger = Logger
        self.logger.debug('initilize {}'.format(self.name))
        self.debug = True
        self.tool_type = tool_type
        self.parent_code = parent_code
        self.testing = testing
        self.jobtext = ['source ~/.bashrc;', 'set -e', 'set -o pipefail', 'echo $PATH']
        self.owner = owner
        self.analysis = analysis
        self.module = None
        self.run_on_node = run_on_node
        self.restart_stage = restart_stage
        self.current_stage = -2
        self.stage_files = defaultdict(list)
        self.child = child
        self.created = datetime.now()
        self.children = []
        self.doc = None
        self.run_dir = None
        self.restart_stage = restart_stage
        self.analysis_type = analysis_type
        self.tool_type = tool_type
        self.config = config
        self.kill_stage = kill_stage
        self.access_code = access_code

        if testing:
            self.num_jobs = 2
        else:
            self.num_jobs = min([threads, mp.cpu_count()])

    def initial_setup(self):
        # Get info on the study/parent analysis from the database
        with Database(owner=self.owner, testing=self.testing) as db:
            if self.restart_stage == 0:
                parent_doc = db.get_doc(self.parent_code)
                self.doc = parent_doc.generate_MMEDSDoc(self.name.split('-')[0], self.tool_type,
                                                        self.analysis_type, self.config, self.access_code)
            else:
                self.doc = db.get_doc(self.access_code)

        self.update_doc(sub_analysis=False, is_alive=True, exit_code=1, pid=self.ident)
        self.doc.save()

        self.path = Path(self.doc.path)
        if self.child:
            self.child_setup()

        self.access_code = self.doc.access_code
        self.path = Path(self.doc.path)
        self.add_path(self.path, key='path')
        write_config(self.doc.config, self.path)
        self.create_qiime_mapping_file()
        self.run_dir = Path('$RUN_{}'.format(self.name.split('-')[0]))

        email = ('email', self.doc.email, self.owner, 'analysis_start',
                 dict(code=self.access_code,
                      analysis='{}-{}'.format(self.doc.tool_type, self.doc.analysis_type),
                      study=self.doc.study_name))
        self.queue.put(email)

    def __str__(self):
        return ppretty(self, seq_length=5)

    def get_info(self):
        """ Method for return a dictionary of relevant info for the process log """
        info = {
            'created': self.created,
            'owner': self.owner,
            'stage': self.restart_stage,
            'study_code': self.doc.study_code,
            'analysis_code': self.doc.access_code,
            'type': self.analysis,
            'pid': self.ident,
            'path': self.doc.path,
            'name': self.name,
            'is_alive': self.is_alive()
        }
        return info

    def update_doc(self, **kwargs):
        """ Pass updates to the database and reload """
        self.doc.modify(**kwargs)
        self.doc.save()
        self.doc.reload()

    def set_stage(self, stage):
        """ Set self.current_stage to the provided value """
        self.current_stage = stage
        self.jobtext.append('echo "MMEDS_STAGE_{}"'.format(stage))

    def add_path(self, name, extension='', key=None, full_path=False):
        """ Add a file or directory with the full path to self.doc. """
        # The path can be indexed by the file name or an explicit key
        if key:
            file_key = key
        else:
            file_key = name

        # The provided 'name' may be a full path, in which case adding the tool path is unnecessary
        if full_path:
            file_path = '{}{}'.format(name, extension)
        else:
            file_path = '{}{}'.format(self.path / name, extension)

        self.doc.files[str(file_key)] = file_path
        self.update_doc(files=self.doc.files)
        self.stage_files[self.current_stage].append(file_key)

    def get_file(self, key, absolute=False, check=False):
        """
        Get the path to the file stored under 'key' relative to the run dir
        :key: A string. The key for accessing the file in the mongo document files dictionary
        :absolute: A boolean. If True return an absolute file path rather than a relative one
        :check: A boolean. If True check that the requested file exists, if it doesn't raise an error
        """
        if check and not Path(self.doc.files[key]).exists():
            raise MissingFileError('No file {} at location {} found.'.format(key, self.doc.files[key]))

        if absolute:
            file_path = Path(self.doc.files[key])
        else:
            try:
                # If it's a parent file this will file
                file_path = self.run_dir / Path(self.doc.files[key]).relative_to(self.path)
            except ValueError:
                # So try again with the parents path
                file_path = self.run_dir / '..' / Path(self.doc.files[key]).relative_to(self.path.parent)
        return file_path

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
            # Wait thirty seconds
            sleep(30)
            # Check bjobs
            jobs = run(['/hpc/lsf/10.1/linux3.10-glibc2.17-x86_64/bin/bjobs'],
                       capture_output=True).stdout.decode('utf-8')
            # If the job is found set it back to true
            if str(job_id) in jobs:
                running = True

    def move_user_files(self):
        """ Move all visualization files intended for the user to a set location. """
        try:
            self.add_path('visualizations_dir', '')
            if not self.get_file('visualizations_dir', True).is_dir():
                self.get_file('visualizations_dir', True).mkdir()
            for key in self.doc.files.keys():
                f = self.get_file(key)
                if '.qzv' in str(self.get_file(key, True)):
                    new_file = f.name
                    copy(self.get_file(key, True), self.get_file('visualizations_dir', True) / new_file)
        except FileNotFoundError as e:
            raise AnalysisError(e.args[1])

    def write_file_locations(self):
        """
        Update the relevant document's metadata and
        create a file_index in the analysis directoy.
        """
        # Create the file index
        with open(self.path / 'file_index.tsv', 'w') as f:
            f.write('{}\t{}\t{}\n'.format(self.doc.owner, self.doc.study_name, self.doc.access_code))
            f.write('Key\tPath\n')
            for key, value in self.doc.files.items():
                f.write('{}\t{}\n'.format(key, value))

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        mmeds_file = self.get_file('metadata', True)

        # Create the Qiime mapping file
        qiime_file = self.path / 'qiime_mapping_file.tsv'
        create_qiime_from_mmeds(mmeds_file, qiime_file, self.doc.tool_type)

        # Add the mapping file to the MetaData object
        self.add_path(qiime_file, key='mapping')

    def summary(self):
        """ Setup script to create summary. """
        self.add_path('summary')
        if self.testing:
            self.jobtext.append('module load mmeds-stable;')
        else:
            self.jobtext.append('module use {}/.modules/modulefiles; module load mmeds-stable;'.format(DATABASE_DIR.parent))
        cmd = [
            'summarize.py ',
            '--path "{}"'.format(self.run_dir),
            '--tool_type {}'.format(self.doc.tool_type)
        ]
        self.jobtext.append(' '.join(cmd))

    def create_sub_analysis(self, category, value):
        """
        Create a child analysis process using only samples that have a particular value
        in a particular metadata column. Handles creating the analysis directory and such
        ===============================
        :category: The column of the metadata to filter by
        :value: The value that :column: must match for a sample to be included
        """
        self.logger.debug('CREATE CHILD {}:{}'.format(category, value))

        child = classcopy(self)
        file_value = camel_case(value)

        # Update process name and children
        child.name = child.name + '-{}-{}'.format(category[1], file_value)
        child.children = []

        with Database(owner=self.owner, testing=self.testing) as db:
            access_code = db.create_access_code(child.name)

        child.doc = self.doc.generate_sub_analysis_doc(category, value, access_code)
        child.path = Path(child.doc.path)

        # Link to the parent's OTU table(s)
        for parent_file in ['otu_table', 'biom_table', 'rep_seqs_table', 'stats_table', 'params']:
            if self.doc.files.get(parent_file) is not None:
                # Add qiime1 specific biom tables
                if 'Qiime1' in self.name and parent_file == 'biom_table':
                    child_file = child.path / 'otu_table.biom'
                    child_file.symlink_to(self.get_file('split_otu_{}'.format(category[1]), True) /
                                          'otu_table__{}_{}__.biom'.format(category[1], value))
                    child.add_path(child_file, key='biom_table')
                else:
                    child_file = child.path / self.get_file(parent_file).name
                    child_file.symlink_to(self.get_file(parent_file, True))
                    child.add_path(child_file, key=parent_file)

        # Handle Qiime1's format of splitting otu tables
        if 'Qiime1' in self.name:
            child.add_path(self.get_file('split_otu_{}'.format(category[1]), True) /
                           'otu_table__{}_{}__.biom'.format(category[1], value),
                           key='parent_table', full_path=True)
        else:
            child.add_path(self.get_file('otu_table', True), key='parent_table', full_path=True)

        # Filter the metadata and write the new file to the childs directory
        mdf = load_metadata(self.get_file('metadata', True))
        new_mdf = mdf.loc[mdf[category] == value]
        write_metadata(new_mdf, child.get_file('metadata', True))

        # Update child's vars
        child.add_path('{}/{}_{}/'.format(child.doc.name, category[1], file_value), '')
        child.run_dir = Path('$RUN_{}_{}_{}'.format(child.doc.name, category[1], file_value))

        # Update the text for the job file
        child.jobtext = deepcopy(self.jobtext)[:6]
        child.jobtext.append('{}={};'.format(str(child.run_dir).replace('$', ''), child.path))

        # Create a new mapping file
        child.create_qiime_mapping_file()

        # Filter the config for the metadata category selected for this sub-analysis
        child.config = deepcopy(child.doc.config)
        child.is_child = True
        write_config(child.doc.config, child.path)

        # Set the parent pid
        child._parent_pid = self.ident
        return child

    def queue_analysis(self, tool_type):
        """
        Add an analysis of the specified type to the watcher queue
        ===============================
        :tool_type: The type of tool to spawn
        """
        self.queue.put(('analysis', self.owner, self.doc.access_code, tool_type,
                        self.config['type'], self.doc.config, self.run_on_node, self.kill_stage))

    def child_setup(self):
        # Update process name and children
        self.name = self.name + '-{}'.format(self.tool_type)

        with Database(owner=self.owner, testing=self.testing) as db:
            parent_doc = db.get_doc(self.parent_code)
            access_code = db.create_access_code(self.name)

        self.doc = parent_doc.generate_analysis_doc(self.name, access_code)
        self.path = Path(self.doc.path)

        # Link to the parent's OTU table(s)
        for parent_file in ['otu_table', 'biom_table', 'rep_seqs_table', 'stats_table', 'params']:
            if parent_doc.files.get(parent_file) is not None:
                self_file = self.path / Path(parent_doc.files[parent_file]).name
                self_file.symlink_to(self.get_file(parent_file, True))
                self.add_path(self_file, key=parent_file)

        self.add_path(self.get_file('otu_table', True), key='parent_table', full_path=True)

        # Filter the metadata and write the new file to the selfs directory
        mdf = load_metadata(parent_doc.files['metadata'])
        write_metadata(mdf, self.get_file('metadata', True))

        # Update self's vars
        self.add_path('{}/{}/'.format(parent_doc.name, self.doc.name), '')
        self.run_dir = Path('$RUN_{}_{}'.format(parent_doc.name, self.doc.name))

        # Update the text for the job file
        self.jobtext = deepcopy(self.jobtext)[:6]
        self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))

        # Create a new mapping file
        self.create_qiime_mapping_file()

        # Filter the config for the metadata category selected for this sub-analysis
        self.config = deepcopy(self.doc.config)
        write_config(self.config, Path(self.doc.path))

    def create_additional_analysis(self, atype):
        """
        Create a child analysis process using only samples that have a particular value
        in a particular metadata column. Handles creating the analysis directory and such
        ===============================
        :category: The column of the metadata to filter by
        :value: The value that :column: must match for a sample to be included
        """
        child = atype(self.owner, self.doc.study_code, atype.__name__.lower(), self.doc.config,
                      self.testing, self.analysis, self.restart_stage, child=True)
        category = None
        value = None
        file_value = None

        # Update process name and children
        child.name = child.name + '-{}'.format(atype.name)
        child.children = []

        # child.doc = self.doc.create_sub_analysis(category, value, access_code)
        child.path = Path(child.doc.path)

        # Link to the parent's OTU table(s)
        for parent_file in ['otu_table', 'biom_table', 'rep_seqs_table', 'stats_table', 'params']:
            if self.doc.files.get(parent_file) is not None:
                # Add qiime1 specific biom tables
                if 'Qiime1' in self.name and parent_file == 'biom_table':
                    child_file = child.path / 'otu_table.biom'
                    child_file.symlink_to(self.get_file('split_otu_{}'.format(category[1]), True) /
                                          'otu_table__{}_{}__.biom'.format(category[1], value))
                    child.add_path(child_file, key='biom_table')
                else:
                    child_file = child.path / self.get_file(parent_file).name
                    child_file.symlink_to(self.get_file(parent_file, True))
                    child.add_path(child_file, key=parent_file)

        # Handle Qiime1's format of splitting otu tables
        if 'Qiime1' in self.name:
            child.add_path(self.get_file('split_otu_{}'.format(category[1]), True) /
                           'otu_table__{}_{}__.biom'.format(category[1], value),
                           key='parent_table', full_path=True)
        else:
            child.add_path(self.get_file('otu_table', True), key='parent_table', full_path=True)

        self.logger.debug('load metadata  {}'.format(self.get_file('metadata', True)))
        # Filter the metadata and write the new file to the childs directory
        mdf = load_metadata(self.get_file('metadata', True))
        new_mdf = mdf.loc[mdf[category] == value]
        write_metadata(new_mdf, child.get_file('metadata', True))
        self.logger.debug('write to {}'.format(child.get_file('metadata', True)))

        # Update child's vars
        if category is None:
            child.add_path('{}/{}/'.format(self.doc.name, child.doc.name), '')
            child.run_dir = Path('$RUN_{}_{}'.format(self.doc.name, child.doc.name))
        else:
            child.add_path('{}/{}_{}/'.format(child.doc.name, category[1], file_value), '')
            child.run_dir = Path('$RUN_{}_{}_{}'.format(child.doc.name, category[1], file_value))

        # Update the text for the job file
        child.jobtext = deepcopy(self.jobtext)[:6]
        child.jobtext.append('{}={};'.format(str(child.run_dir).replace('$', ''), child.path))

        # Create a new mapping file
        child.create_qiime_mapping_file()

        # Filter the config for the metadata category selected for this sub-analysis
        child.config = deepcopy(child.doc.config)
        child.is_child = True
        child.write_config()

        # Set the parent pid
        child._parent_pid = self.get_indent()
        return child

    def create_children(self):
        """ Create child analysis processes """
        mdf = load_metadata(self.get_file('metadata', True))

        # For each column selected...
        for col in self.doc.config['sub_analysis']:
            self.logger.debug('Create child for col {}'.format(col))
            try:
                t_col = (COL_TO_TABLE[col], col)
            # Additional columns won't be in this table
            except KeyError:
                t_col = ('AdditionalMetaData', col)
            # For each value in the column, create a sub-analysis
            for val, df in mdf.groupby(t_col):
                child = self.create_sub_analysis(t_col, val)
                self.children.append(child)
        self.logger.debug('finished creating children')

    def start_children(self):
        """ Start running the child processes. Limiting the concurrent processes to self.num_jobs """
        for child in self.children:
            self.logger.debug('I am {}, this tool is {}, my childs parent is {}'.format(os.getpid(),
                                                                                        self.ident,
                                                                                        child._parent_pid))
            child.start()

    def wait_on_children(self):
        """ Wait for all child analyses """
        for child in self.children:
            child.join()

    def setup_analysis(self, summary=True):
        """ Create the summary of the analysis """
        if summary:
            self.summary()
        self.jobtext.append('echo "MMEDS_FINISHED"')

        submitfile = self.path / 'submitfile'
        self.add_path(submitfile, '.sh', 'submitfile')

        # Define the job and error files
        count = 0
        jobfile = self.path / 'jobfile_{}.lsf'.format(count)
        while jobfile.exists():
            jobfile = self.path / 'jobfile_{}.lsf'.format(count)
            count += 1
        self.add_path(jobfile, key='jobfile')

        if self.testing:
            # Setup the error log in a testing environment
            count = 0
            errorlog = self.path / 'errorlog_{}.err'.format(count)
            while errorlog.exists():
                errorlog = self.path / 'errorlog_{}.err'.format(count)
                count += 1
            self.add_path(errorlog, key='errorlog')
            # Open the jobfile to write all the commands
            jobfile.write_text('\n'.join(['#!/bin/bash -l'] + self.jobtext))
            # Set execute permissions
            jobfile.chmod(0o770)
        else:
            errorlog = self.path / '{}-{}.stdout'.format(self.owner, self.doc.name)
            self.add_path(errorlog, key='errorlog')
            self.logger.debug('In run_analysis')
            # Get the job header text from the template
            temp = JOB_TEMPLATE.read_text()
            # Write all the commands
            jobfile.write_text('\n'.join([temp.format(**self.get_job_params())] + self.jobtext))
        self.doc.save(validate=True)

    def run_analysis(self):
        """ Runs the setup, and starts the analysis process """
        try:
            self.setup_analysis()
            if self.doc.sub_analysis:
                self.logger.debug('I am a sub analysis {}'.format(self.name))
                # Wait for the otu table to show up
                while not self.get_file('parent_table', True).exists():
                    self.logger.debug('I {} wait on {} to exist'.format(self.name, self.get_file('parent_table', True)))
                    sleep(20)
                self.logger.debug('I {} have awoken'.format(self.name))
            jobfile = self.get_file('jobfile', True)
            self.write_file_locations()

            self.logger.debug(self.doc.config['sub_analysis'])
            # Start the sub analyses if so configured
            if not self.doc.config['sub_analysis'] == 'None':
                self.logger.debug('I am not a sub analysis {}'.format(self.name))
                self.create_children()
                self.start_children()
                self.logger.debug([child.name for child in self.children])

            self.update_doc(analysis_status='started')
            type_ron = type(self.run_on_node)
            self.logger.error(f'testing: {self.testing}, ron: {self.run_on_node} (type) {type_ron}')
            if self.testing or not (self.run_on_node == -1):
                self.logger.debug('I {} am about to run'.format(self.name))
                jobfile.chmod(0o770)
                # Send the output to the error log
                with open(self.get_file('errorlog', True), 'w+', buffering=1) as f:
                    # Run the command
                    run([jobfile], stdout=f, stderr=f)
                self.logger.debug('I {} have finished running'.format(self.name))
            else:
                # Create a file to execute the submission
                submitfile = self.get_file('submitfile', True)
                submitfile.write_text('\n'.join(['#!/bin/bash -l', 'bsub < {};'.format(jobfile)]))
                # Set execute permissions
                submitfile.chmod(0o770)
                jobfile.chmod(0o770)

                output = run([submitfile], check=True, capture_output=True)
                self.logger.debug('Submitted job {}'.format(output.stdout))
                job_id = int(str(output.stdout).split(' ')[1].strip('<>'))
                self.logger.error(job_id)
                self.wait_on_job(job_id)

            self.logger.debug('{}: pre post analysis'.format(self.name))
            self.post_analysis()
            self.logger.debug('{}: post post analysis'.format(self.name))
        except CalledProcessError as e:
            self.move_user_files()
            self.write_file_locations()
            raise AnalysisError(e.args[0])

    def post_analysis(self):
        """ Perform checking and house keeping once analysis finishes """
        log_text = self.get_file('errorlog', True).read_text()
        # Raise an error if the final command doesn't run
        if 'MMEDS_FINISHED' not in log_text:
            self.update_doc(exit_code=1)
            self.logger.debug('{}: Analysis did not finish'.format(self.name))
            # Count the check points in the output to determine where to restart from
            stage = 0
            for i in range(1, 6):
                if 'MMEDS_STAGE_{}'.format(i) in log_text:
                    stage = i
            self.update_doc(restart_stage=stage)
            # Files removed
            deleted = []
            # TODO Move this to happen when an anlysis is restarted
            # Go through all files in the analysis
            for stage, files in self.stage_files.items():
                self.logger.debug('{}: Stage: {}, Files: {}'.format(self.name, stage, files))
                # If they should be created after the last checkpoint
                if stage >= self.doc.restart_stage:
                    self.logger.debug('{}: Greater than restart stage'.format(self.name))
                    for f in files:
                        if not f == 'jobfile' and not f == 'errorlog':
                            deleted.append(f)
                            # Check if they exist
                            unfinished = self.get_file(f, True)
                            self.logger.debug('{}: checking file {}'.format(self.name, unfinished))
                            if unfinished.exists():
                                self.logger.debug('{}: file exists'.format(self.name))
                                # Otherwise delete them
                                if unfinished.is_dir():
                                    self.logger.debug('{}: rmtree'.format(self.name))
                                    rmtree(unfinished)
                                else:
                                    self.logger.debug('{}: unlink'.format(self.name))
                                    unfinished.unlink()
                            else:
                                self.logger.debug('{}: file does exist {}'.format(self.name, unfinished))
                else:
                    self.logger.debug('{}: stage already passed'.format(self.name))

            # Remove the deleted files from the mongodb document for the analysis
            finished_files = self.doc.files
            for key in deleted:
                del finished_files[key]
            self.update_doc(files=finished_files)

            self.logger.debug('{}: finished file cleanup'.format(self.name))

            email = ('email', self.doc.email, self.doc.owner, 'error',
                     dict(code=self.doc.access_code,
                          analysis='{}-{}'.format(self.doc.tool_type, self.doc.analysis_type),
                          stage=self.doc.restart_stage,
                          study=self.doc.study_name))
            self.queue.put(email)
            raise AnalysisError('{} failed during stage {}'.format(self.name, self.doc.restart_stage))

        email = ('email', self.doc.email, self.doc.owner, 'analysis_done',
                 dict(code=self.doc.access_code,
                      analysis='{}-{}'.format(self.doc.tool_type, self.doc.analysis_type),
                      study=self.doc.study_name))
        self.queue.put(email)
        self.update_doc(restart_stage=-1)  # Indicates analysis finished successfully
        self.move_user_files()

    def run(self):
        """ Overrides Process.run() """
        # Unless all of run completes succesfully exit code should be 1
        exit_code = 1
        try:
            self.logger.debug('{} calling run'.format(self.name))
            self.initial_setup()
            self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))
            self.logger.debug('Finished initial setup')
            if self.analysis:
                self.logger.debug('I {} am running analysis'.format(self.name))
                self.run_analysis()
            else:
                self.logger.debug('I {} am setting up analysis'.format(self.name))
                self.setup_analysis()
            exit_code = 0  # Tool as completed successfully
        finally:
            # Update the related document that the process as terminated
            self.update_doc(pid=None, is_alive=False, analysis_status='Finished', exit_code=exit_code)


class TestTool(Tool):
    """ A class for running tool methods during testing """

    def __init__(self, queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, run_on_node,
                 analysis=True, restart_stage=0, kill_stage=-1, time=20):
        super().__init__(queue, owner, access_code, parent_code, tool_type, analysis_type, config, testing, run_on_node,
                         analysis=analysis, restart_stage=restart_stage)
        print('Creating test tool with restart stage {} and time {}'.format(restart_stage, time))
        self.time = time

    def run_analysis(self):
        sleep(int(self.time))

    def setup_analysis(self):
        sleep(int(self.doc.analysis_type) / 10)
