from pathlib import Path
from subprocess import run, CalledProcessError
from shutil import copy, rmtree
from psutil import pid_exists
from time import sleep
from copy import copy as classcopy
from copy import deepcopy
from ppretty import ppretty
from collections import defaultdict
from datetime import datetime

from mmeds.database import Database
from mmeds.util import (create_qiime_from_mmeds, write_config,
                        load_metadata, write_metadata, camel_case,
                        send_email)
from mmeds.error import AnalysisError, MissingFileError
from mmeds.config import COL_TO_TABLE, JOB_TEMPLATE
from mmeds.log import MMEDSLog

import multiprocessing as mp
import os

logger = MMEDSLog('debug').logger


class Tool(mp.Process):
    """
    The base class for tools used by mmeds inherits the python Process class.
    self.run is overridden by the classes that inherit from Tool so the analysis
    will happen in seperate processes.
    """

    def __init__(self, owner, parent_code, tool_type, analysis_type, config, testing,
                 threads=10, analysis=True, child=False, restart_stage=0):
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
        logger.debug('initilize {}'.format(self.name))
        self.debug = True
        self.parent_code = parent_code
        self.testing = testing
        self.jobtext = ['source ~/.bashrc;', 'set -e', 'set -o pipefail', 'echo $PATH']
        self.owner = owner
        self.analysis = analysis
        self.module = None
        self.restart_stage = restart_stage
        self.current_stage = -2
        self.stage_files = defaultdict(list)
        self.created = datetime.now()
        self.children = []

        if testing:
            self.num_jobs = 2
        else:
            self.num_jobs = min([threads, mp.cpu_count()])

        # Get info on the study/parent analysis from the database
        with Database(owner=self.owner, testing=self.testing) as db:
            if restart_stage == 0:
                parent_doc = db.get_doc(self.parent_code)
                logger.debug('Generating doc from')
                logger.debug(parent_doc)
                logger.debug(parent_doc.files.keys())
                access_code = db.create_access_code(self.name)
                self.doc = parent_doc.generate_MMEDSDoc(self.name.split('-')[0], tool_type,
                                                        analysis_type, config, access_code)
            else:
                self.doc = db.get_doc(self.parent_code)

        self.path = Path(self.doc.path)

        logger.debug('Doc creation date: {}'.format(self.doc.created))
        self.access_code = self.doc.access_code
        self.path = Path(self.doc.path)
        self.add_path(self.path, key='path')
        write_config(self.doc.config, self.path)
        self.create_qiime_mapping_file()
        self.doc.sub_analysis = False
        self.run_dir = Path('$RUN_{}'.format(self.name.split('-')[0]))

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
            'pid': self.pid,
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
        logger.debug('unzipping files for code {}'.format(self.doc.access_code))
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
            logger.debug('Move analysis files into directory')
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
        create_qiime_from_mmeds(mmeds_file, qiime_file, self.doc.doc_type)

        # Add the mapping file to the MetaData object
        self.add_path(qiime_file, key='mapping')

    def summary(self):
        """ Setup script to create summary. """
        self.add_path('summary')
        self.jobtext.append(self.module.replace('load', 'unload'))
        self.jobtext.append('module load mmeds-stable;')
        cmd = [
            'summarize.py ',
            '--path "{}"'.format(self.run_dir),
            '--tool_type {}'.format(self.doc.doc_type.split('-')[0])
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
        logger.debug('CREATE CHILD {}:{}'.format(category, value))

        child = classcopy(self)
        file_value = camel_case(value)

        # Update process name and children
        child.name = child.name + '-{}-{}'.format(category[1], file_value)
        child.children = []

        with Database(owner=self.owner, testing=self.testing) as db:
            access_code = db.create_access_code(child.name)
        logger.debug('CHILD ACCESS CODE {}'.format(access_code))

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

        logger.debug('load metadata  {}'.format(self.get_file('metadata', True)))
        # Filter the metadata and write the new file to the childs directory
        mdf = load_metadata(self.get_file('metadata', True))
        new_mdf = mdf.loc[mdf[category] == value]
        write_metadata(new_mdf, child.get_file('metadata', True))
        logger.debug('write to {}'.format(child.get_file('metadata', True)))

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
        child._parent_pid = self.pid
        return child

    def create_analysis(self, atype):
        """
        Create a child analysis process using only samples that have a particular value
        in a particular metadata column. Handles creating the analysis directory and such
        ===============================
        :category: The column of the metadata to filter by
        :value: The value that :column: must match for a sample to be included
        """
        logger.debug('creating child of {}'.format(atype))
        child = atype(self.owner, self.doc.study_code, atype.__name__.lower(), self.doc.analysis_type,
                      self.doc.config, self.testing, analysis=self.analysis, restart_stage=self.restart_stage,
                      child=True)
        logger.debug('finished child creation')
        logger.debug(child)

        # Update process name and children
        child.name = child.name + '-{}'.format(atype.__name__)
        child.children = []

        with Database(owner=self.owner, testing=self.testing) as db:
            access_code = db.create_access_code(child.name)
        logger.debug('CHILD ACCESS CODE {}'.format(access_code))
        child.doc = self.doc.generate_analysis_doc(atype.__name__, access_code)  # TODO
        child.path = Path(child.doc.path)

        # Link to the parent's OTU table(s)
        for parent_file in ['otu_table', 'biom_table', 'rep_seqs_table', 'stats_table', 'params']:
            if self.doc.files.get(parent_file) is not None:
                child_file = child.path / self.get_file(parent_file).name
                child_file.symlink_to(self.get_file(parent_file, True))
                child.add_path(child_file, key=parent_file)

        child.add_path(self.get_file('otu_table', True), key='parent_table', full_path=True)

        logger.debug('load metadata  {}'.format(self.get_file('metadata', True)))
        # Filter the metadata and write the new file to the childs directory
        mdf = load_metadata(self.get_file('metadata', True))
        write_metadata(mdf, child.get_file('metadata', True))
        logger.debug('write to {}'.format(child.get_file('metadata', True)))

        # Update child's vars
        child.add_path('{}/{}/'.format(self.doc.name, child.doc.name), '')
        child.run_dir = Path('$RUN_{}_{}'.format(self.doc.name, child.doc.name))

        # Update the text for the job file
        child.jobtext = deepcopy(self.jobtext)[:6]
        child.jobtext.append('{}={};'.format(str(child.run_dir).replace('$', ''), child.path))

        # Create a new mapping file
        child.create_qiime_mapping_file()

        # Filter the config for the metadata category selected for this sub-analysis
        child.config = deepcopy(child.doc.config)
        child.is_child = True
        write_config(child.config, Path(child.doc.path))

        # Set the parent pid
        child._parent_pid = self.pid
        return child

    def create_additional_analysis(self, atype):
        """
        Create a child analysis process using only samples that have a particular value
        in a particular metadata column. Handles creating the analysis directory and such
        ===============================
        :category: The column of the metadata to filter by
        :value: The value that :column: must match for a sample to be included
        """
        logger.debug('creating child of {}'.format(atype))
        child = atype(self.owner, self.doc.study_code, atype.__name__.lower(), self.doc.config,
                      self.testing, self.analysis, self.restart_stage, child=True)
        logger.debug('finished child creation')
        logger.debug(child)
        category = None
        value = None
        file_value = None

        # Update process name and children
        child.name = child.name + '-{}'.format(atype.name)
        child.children = []

        with Database(owner=self.owner, testing=self.testing) as db:
            access_code = db.create_access_code(child.name)
        logger.debug('CHILD ACCESS CODE {}'.format(access_code))

        logger.debug('MY DOC')
        logger.debug(self.doc)
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

        logger.debug('load metadata  {}'.format(self.get_file('metadata', True)))
        # Filter the metadata and write the new file to the childs directory
        mdf = load_metadata(self.get_file('metadata', True))
        new_mdf = mdf.loc[mdf[category] == value]
        write_metadata(new_mdf, child.get_file('metadata', True))
        logger.debug('write to {}'.format(child.get_file('metadata', True)))

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
        child._parent_pid = self.pid
        return child

    def create_children(self):
        """ Create child analysis processes """
        mdf = load_metadata(self.get_file('metadata', True))

        # For each column selected...
        for col in self.doc.config['sub_analysis']:
            logger.debug('Create child for col {}'.format(col))
            try:
                t_col = (COL_TO_TABLE[col], col)
            # Additional columns won't be in this table
            except KeyError:
                t_col = ('AdditionalMetaData', col)
            # For each value in the column, create a sub-analysis
            for val, df in mdf.groupby(t_col):
                child = self.create_sub_analysis(t_col, val)
                self.children.append(child)
        logger.debug('finished creating children')

    def start_children(self):
        """ Start running the child processes. Limiting the concurrent processes to self.num_jobs """
        for child in self.children:
            logger.debug('I am {}, this tool is {}, my childs parent is {}'.format(os.getpid(),
                                                                                   self.pid,
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

        count = 0
        error_log = self.path / 'errorlog_{}.err'.format(count)
        while error_log.exists():
            error_log = self.path / 'errorlog_{}.err'.format(count)
            count += 1
        self.add_path(error_log, key='errorlog')

        if self.testing:
            # Open the jobfile to write all the commands
            jobfile.write_text('\n'.join(['#!/bin/bash -l'] + self.jobtext))
            # Set execute permissions
            jobfile.chmod(0o770)
        else:
            logger.debug('In run_analysis')
            # Get the job header text from the template
            temp = JOB_TEMPLATE.read_text()
            # Write all the commands
            jobfile.write_text('\n'.join([temp.format(**self.get_job_params())] + self.jobtext))

    def run_analysis(self):
        """ Runs the setup, and starts the analysis process """
        try:
            self.setup_analysis()
            if self.doc.sub_analysis:
                logger.debug('I am a sub analysis {}'.format(self.name))
                # Wait for the otu table to show up
                while not self.get_file('parent_table', True).exists():
                    if not pid_exists(self._parent_pid):
                        logger.debug('Parent died prior to completion, self destructing')
                        self.terminate()
                    logger.debug('I {} wait on {} to exist'.format(self.name, self.get_file('parent_table', True)))
                    sleep(20)
                logger.debug('I {} have awoken'.format(self.name))
            jobfile = self.get_file('jobfile', True)
            self.write_file_locations()

            logger.debug(self.doc.config['sub_analysis'])
            # Start the sub analyses if so configured
            if not self.doc.config['sub_analysis'] == 'None':
                logger.debug('I am not a sub analysis {}'.format(self.name))
                self.create_children()
                self.start_children()
                logger.debug([child.name for child in self.children])

            if self.testing:
                self.update_doc(analysis_status='started')
                logger.debug('I {} am about to run'.format(self.name))
                # Send the output to the error log
                with open(self.get_file('errorlog', True), 'w+', buffering=1) as f:
                    # Run the command
                    run([jobfile], stdout=f, stderr=f)
                logger.debug('I {} have finished running'.format(self.name))
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
            logger.debug('{}: pre post analysis'.format(self.name))
            self.post_analysis()
            logger.debug('{}: post post analysis'.format(self.name))
        except CalledProcessError as e:
            self.move_user_files()
            self.write_file_locations()
            raise AnalysisError(e.args[0])

    def post_analysis(self):
        """ Perform checking and house keeping once analysis finishes """
        log_text = self.get_file('errorlog', True).read_text()
        # Raise an error if the final command doesn't run
        if 'MMEDS_FINISHED' not in log_text:
            logger.debug('{}: Analysis did not finish'.format(self.name))
            # Count the check points in the output to determine where to restart from
            stage = 0
            for i in range(1, 6):
                if 'MMEDS_STAGE_{}'.format(i) in log_text:
                    stage = i
            self.update_doc(restart_stage=stage)
            # Files removed
            deleted = []
            # Go through all files in the analysis
            for stage, files in self.stage_files.items():
                logger.debug('{}: Stage: {}, Files: {}'.format(self.name, stage, files))
                # If they should be created after the last checkpoint
                if stage >= self.doc.restart_stage:
                    logger.debug('{}: Greater than restart stage'.format(self.name))
                    for f in files:
                        if not f == 'jobfile' and not f == 'errorlog':
                            deleted.append(f)
                            # Check if they exist
                            unfinished = self.get_file(f, True)
                            logger.debug('{}: checking file {}'.format(self.name, unfinished))
                            if unfinished.exists():
                                logger.debug('{}: file exists'.format(self.name))
                                # Otherwise delete them
                                if unfinished.is_dir():
                                    logger.debug('{}: rmtree'.format(self.name))
                                    rmtree(unfinished)
                                else:
                                    logger.debug('{}: unlink'.format(self.name))
                                    unfinished.unlink()
                            else:
                                logger.debug('{}: file does exist {}'.format(self.name, unfinished))
                else:
                    logger.debug('{}: stage already passed'.format(self.name))

            # Remove the deleted files from the mongodb document for the analysis
            finished_files = self.doc.files
            for key in deleted:
                del finished_files[key]
            self.update_doc(files=finished_files)

            logger.debug('{}: finished file cleanup'.format(self.name))

            send_email(self.doc.email, self.doc.owner, message='error', code=self.doc.access_code,
                       stage=self.doc.restart_stage, testing=self.testing, study=self.doc.study_name)
            raise AnalysisError('{} failed during stage {}'.format(self.name, self.doc.restart_stage))
        send_email(self.doc.email, self.doc.owner, message='analysis_done', code=self.doc.access_code,
                   testing=self.testing, study=self.doc.study_name)
        self.update_doc(restart_stage=-1)  # Indicates analysis finished successfully
        self.move_user_files()

        if not self.testing:
            send_email(self.doc.email,
                       self.doc.owner,
                       'analysis',
                       doc_type=self.name + self.doc.doc_type,
                       study_name=self.doc.study_name,
                       testing=self.testing)

    def run(self):
        """ Overrides Process.run() """
        logger.debug('{} calling run'.format(self.name))
        self.update_doc(pid=self.pid)
        if self.analysis:
            logger.debug('I {} am running analysis'.format(self.name))
            self.run_analysis()
        else:
            logger.debug('I {} am setting up analysis'.format(self.name))
            self.setup_analysis()
        self.update_doc(pid=None, analysis_status='Finished')


class TestTool(Tool):
    """ A class for running tool methods during testing """

    def __init__(self, owner, access_code, tool_type, analysis_type, config, testing,
                 analysis=True, restart_stage=0, kill_stage=-1, time=5):
        super().__init__(owner, access_code, tool_type, analysis_type, config, testing,
                         analysis=analysis, restart_stage=restart_stage)
        self.time = time

    def run(self):
        sleep(self.time)
