from pathlib import Path
from subprocess import run, CalledProcessError
from shutil import copy, rmtree
from time import sleep
from copy import copy as classcopy
from copy import deepcopy
from ppretty import ppretty
from collections import defaultdict
from datetime import datetime
import pandas as pd

from mmeds.database.database import Database
from mmeds.util import (create_qiime_from_mmeds, write_config,
                        load_metadata, write_metadata, camel_case,
                        get_file_index_entry_location, get_mapping_file_subset)
from mmeds.error import AnalysisError, MissingFileError
from mmeds.config import (COL_TO_TABLE, JOB_TEMPLATE, WORKFLOWS, SNAKEMAKE_WORKFLOWS_DIR,
                          SNAKEMAKE_RULES_DIR, TAXONOMIC_DATABASES)
from mmeds.logging import Logger

import multiprocessing as mp

import os


class Analysis(mp.Process):
    """
    The base class for tools used by mmeds inherits the python Process class.
    Process.run is overridden by the classes that inherit from Tool so the analysis
    will happen in seperate processes when Process.start() is called.
    """

    def __init__(self, queue, owner, access_code, study_code, workflow_type, analysis_type, analysis_name, config,
                 testing, runs, run_on_node, threads=10, analysis=True, restart_stage=0, kill_stage=-1):
        """
        Setup the Analysis class
        ====================
        :owner: A string. The owner of the files being analyzed.
        :atype: A string. The type of analysis to perform. Qiime1 or 2, DADA2 or DeBlur.
        :config: A file object. A custom config file, may be None.
        :testing: A boolean. If True run with configurations for a local server.
        :runs: a dictionary of sequencing runs with their paths and files
        :threads: An int. The number of threads to use during analysis, is overwritten if testing==True.
        :analysis: A boolean. If True run a new analysis, if false just summarize the previous analysis.
        :access_code: A string. If this analysis is being restarted from a previous analysis then this
            will be the access_code for the previous document
        :restart_stage: An int. Refers to the stage the analysis should be restarted from. The stages are
            indicated via echo statements in the jobfile.
        :kill_stage: An int. Indicates at what point in an analysis the process should automatically
            terminate, if any. Not used in production, only when testing.
        """
        super().__init__()
        self.queue = queue
        self.logger = Logger
        Logger.debug('initilize {}'.format(self.name))
        self.debug = True
        self.workflow_type = workflow_type
        self.testing = testing
        self.jobtext = ['source ~/.bashrc;', 'set -e', 'set -o pipefail', 'echo $PATH']
        self.owner = owner
        self.analysis = analysis
        self.run_on_node = run_on_node
        self.restart_stage = restart_stage
        self.current_stage = -2
        self.stage_files = defaultdict(list)
        self.created = datetime.now()
        self.doc = None
        self.run_dir = None
        self.restart_stage = restart_stage
        self.analysis_type = analysis_type
        self.analysis_name = analysis_name
        self.config = config
        self.kill_stage = kill_stage
        self.access_code = access_code
        self.study_code = study_code
        self.sequencing_runs = runs
        self.num_jobs = min([threads, mp.cpu_count()])

    def __str__(self):
        """ Provides a nicely formatted string representation of a Tool process """
        return ppretty(self, seq_length=5)

    ###################
    # General Utility #
    ###################

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
        """ Passes updates to the database and reloads """
        self.doc.modify(**kwargs)
        self.doc.save()
        self.doc.reload()

    def add_path(self, name, extension='', key=None, full_path=False):
        """
        Add a file or directory with the full path to self.doc.
        =======================================================
        :name: This is just the basename of the path, no extensions
        :extension: The extension the path should be given if it's a file.
            If none is provided the path is assumed to be a directory
        :key: The key the file should be given in `self.doc.files`.
            If nothing is provided for this argument it will default to the value of :name:
        :full_path: If True then :name: should contain the full path to the given file
            or directory. When False (the default) :name: is thought to only be the
            basename of the file or directory and the location of it is assumed to
            be the base directory of the analysis.
        """
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
        ===================================================================
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

    def get_job_params(self):
        """
        Get the parameters to use when submitting the jobfile. Right now the same set of defaults
        is used for every analysis but potentially in future these could be set via the config file.
        """
        params = {
            'walltime': '20:00',
            'jobname': '{}-{}'.format(self.owner, self.doc.name),
            'path': self.path,
            'nodes': self.num_jobs,
            'memory': 50000,
            'queue': 'premium'
        }
        return params

    def queue_analysis(self, workflow_type):
        """
        Add an analysis of the specified type to the watcher queue
        ===============================
        :workflow_type: The type of tool to spawn
        """
        self.queue.put(('analysis', self.owner, self.doc.access_code, workflow_type,
                        self.config['type'], self.doc.config, self.run_on_node, self.kill_stage))

    ############################
    # Analysis File Management #
    ############################

    def write_file_locations(self):
        """
        This writes all the information contained in self.doc.files to a file on disk.
        This is necessary for making the summaries portable. I also find it can be
        helpful when investigating issues with analysis manually.
        """
        # Create the file index
        with open(self.path / 'file_index.tsv', 'w') as f:
            f.write('{}\t{}\t{}\n'.format(self.doc.owner, self.doc.study_name, self.doc.access_code))
            f.write('Key\tPath\n')
            for key, value in self.doc.files.items():
                f.write('{}\t{}\n'.format(key, value))

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the MMEDS metadata """
        # Open the metadata file for the study
        mmeds_file = self.get_file('metadata', True)

        # Create the Qiime mapping file
        qiime_file = self.get_file("tables_dir", True) / 'qiime_mapping_file.tsv'
        create_qiime_from_mmeds(mmeds_file, qiime_file, self.doc.workflow_type)

        # Add the mapping file to the MetaData object
        self.add_path(qiime_file, key='mapping')

    def create_snakemake_file(self):
        """ Copy a snakemake Snakefile to be used for analysis """
        workflow_file = SNAKEMAKE_WORKFLOWS_DIR / f"{self.workflow_type}.Snakefile"
        # Open file for copying
        with open(workflow_file, "rt") as f:
            workflow_text = f.read()

        # Specify directory with snakemake rules
        workflow_text = workflow_text.format(snakemake_dir=SNAKEMAKE_RULES_DIR)

        # Write new Snakefile in analysis directory
        snakefile = self.path / "Snakefile"
        self.add_path(snakefile, key="snakefile")
        with open(snakefile, "wt") as f:
            f.write(workflow_text)

    def copy_taxonomic_database(self):
        """ Copy in the database (e.g. greengenes, silva) to be used for classification"""
        database_file = TAXONOMIC_DATABASES[self.config["taxonomic_database"]]
        database_copy = self.get_file("tables_dir", True) / database_file.name
        self.add_path(database_copy, key="taxonomic_database")
        copy(database_file, database_copy)

    def link_feature_tables(self):
        """ Symlink to feature tables that were generated in a previous analysis """
        with Database(owner=self.owner, testing=self.testing) as db:
            previous_analyses = list(db.get_all_analyses_from_study(self.study_code))

        tables_dir = self.get_file("tables_dir", True)
        for table in self.config["tables"]:
            self.add_path(tables_dir / f"{table}.qza", key=table)
            table_files = []
            for doc in previous_analyses:
                analysis_dir = Path(doc["path"])
                table_files += list(analysis_dir.glob(f"**/{table}.qza"))

            if len(table_files) < 1:
                raise MissingFileError(f"No file named {table}.qza in previous analyses of study {self.doc.study_name}")

            #TODO: Handle more than 1 matching file
            self.get_file(table, True).symlink_to(table_files[0])

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

    def make_analysis_dirs(self):
        self.add_path(self.path / 'tables', key="tables_dir")
        tables_dir = self.get_file("tables_dir", True)
        if not tables_dir.is_dir():
            tables_dir.mkdir()

    ##############################
    # Analysis Execution Control #
    ##############################

    def initial_setup(self):
        """
        Perform initial setup for an analysis process. This includes creating a MMEDSDoc if
        one doesn't already exist (happens when restarting). Also creates a directory for the
        analysis
        """
        # Get info on the study/parent analysis from the database
        with Database(owner=self.owner, testing=self.testing) as db:
            if self.restart_stage == 0:
                parent_doc = db.get_doc(self.study_code)
                self.doc = parent_doc.generate_MMEDSDoc(self.name.split('-')[0], self.workflow_type, self.analysis_type,
                                                        self.config, self.access_code, self.analysis_name)
            else:
                self.doc = db.get_doc(self.access_code)

        # Update the document with the most current information on this analysis
        self.update_doc(sub_analysis=False, is_alive=True, exit_code=1, pid=self.ident)
        self.doc.save()

        self.path = Path(self.doc.path)

        self.access_code = self.doc.access_code
        self.path = Path(self.doc.path)
        self.add_path(self.path, key='path')

        self.make_analysis_dirs()

        # This is somewhere issues can arrive. If there are problematic differences
        # between the config file as it was uploaded, and what the analysis is running
        # from, `write_config` likely had something to do with it.
        write_config(self.doc.config, self.path)
        self.create_qiime_mapping_file()

        # Add handling for raw data if used by the workflow
        if "sequencing_runs" in WORKFLOWS[self.workflow_type]["parameters"]:
            self.split_by_sequencing_run()

        if "taxonomic_database" in WORKFLOWS[self.workflow_type]["parameters"]:
            self.copy_taxonomic_database()

        if "tables" in WORKFLOWS[self.workflow_type]["parameters"]:
            self.link_feature_tables()

        self.create_snakemake_file()
        self.run_dir = Path('$RUN_{}'.format(self.name.split('-')[0]))

    def setup_analysis(self, summary=False):
        """ Setup error logs and jobfile. """
        Logger.debug("setting up analysis")
        self.jobtext.append(f"cd {self.run_dir}")
        if self.testing:
            self.jobtext.append("sleep 2")
        self.jobtext.append("ml anaconda3/2024.06")
        self.jobtext.append("conda activate mmeds_test")
        self.jobtext.append("snakemake --dag | dot -Tpdf >| snakemake_dag.pdf")
        self.jobtext.append("snakemake --rulegraph | dot -Tpdf >| snakemake_rulegraph.pdf")
        self.jobtext.append(f"snakemake --use-conda --cores {self.num_jobs} --default-resource tmpdir=\"tmp_dir\" -k")
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
        Logger.debug("created job and submit files")

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
            Logger.debug('In run_analysis')
            # Get the job header text from the template
            temp = JOB_TEMPLATE.read_text()
            # Write all the commands
            jobfile.write_text('\n'.join([temp.format(**self.get_job_params())] + self.jobtext))
        self.doc.save(validate=True)

    def run_analysis(self):
        """ Runs the setup, and starts the analysis process """
        try:
            self.setup_analysis()
            jobfile = self.get_file('jobfile', True)
            self.write_file_locations()

            self.update_doc(analysis_status='started')
            type_ron = type(self.run_on_node)
            Logger.error(f'testing: {self.testing}, ron: {self.run_on_node} (type) {type_ron}')

            # Tell the watcher to send an email that the analysis has started.
            email = ('email', self.doc.email, self.owner, 'analysis_start',
                     dict(code=self.access_code,
                          analysis='{}-{}'.format(self.doc.workflow_type, self.doc.analysis_type),
                          study=self.doc.study_name))
            self.queue.put(email)

            if self.testing or not (self.run_on_node == -1):
                Logger.debug('I {} am about to run'.format(self.name))
                jobfile.chmod(0o770)
                with open(jobfile, 'r') as f:
                    Logger.debug(f"Jobfile:\n{f.read()}")
                # Send the output to the error log
                with open(self.get_file('errorlog', True), 'w+', buffering=1) as f:
                    # Run the command
                    run([jobfile], stdout=f, stderr=f)
                with open(self.get_file('errorlog', True), 'r') as f:
                    Logger.debug(f"Job stdout/err:\n{f.read()}")
                Logger.debug('I {} have finished running'.format(self.name))
            else:
                # Create a file to execute the submission
                submitfile = self.get_file('submitfile', True)
                submitfile.write_text('\n'.join(['#!/bin/bash -l', 'bsub < {};'.format(jobfile)]))
                # Set execute permissions
                submitfile.chmod(0o770)
                jobfile.chmod(0o770)

                output = run([submitfile], check=True, capture_output=True)
                Logger.debug('Submitted job {}'.format(output.stdout))
                job_id = int(str(output.stdout).split(' ')[1].strip('<>'))
                Logger.error(job_id)
                self.wait_on_job(job_id)

            Logger.debug('{}: pre post analysis'.format(self.name))
            self.post_analysis()
            Logger.debug('{}: post post analysis'.format(self.name))
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
            Logger.debug('{}: Analysis did not finish'.format(self.name))
            # Count the check points in the output to determine where to restart from
            stage = 0
            for i in range(1, 6):
                if 'MMEDS_STAGE_{}'.format(i) in log_text:
                    stage = i
            self.update_doc(restart_stage=stage)

            # TODO: Find a use for this, disabled because it deletes files we want
            # TODO Move this to happen when an analysis is restarted
            if False:
                # Files removed
                deleted = []
                # Go through all files in the analysis
                for stage, files in self.stage_files.items():
                    Logger.debug('{}: Stage: {}, Files: {}'.format(self.name, stage, files))
                    # If they should be created after the last checkpoint
                    if stage >= self.doc.restart_stage:
                        Logger.debug('{}: Greater than restart stage'.format(self.name))
                        for f in files:
                            if not f == 'jobfile' and not f == 'errorlog':
                                deleted.append(f)
                                # Check if they exist
                                unfinished = self.get_file(f, True)
                                Logger.debug('{}: checking file {}'.format(self.name, unfinished))
                                if unfinished.exists():
                                    Logger.debug('{}: file exists'.format(self.name))
                                    # Otherwise delete them
                                    if unfinished.is_dir():
                                        Logger.debug('{}: rmtree'.format(self.name))
                                        rmtree(unfinished)
                                    else:
                                        Logger.debug('{}: unlink'.format(self.name))
                                        unfinished.unlink()
                                else:
                                    Logger.debug('{}: file does exist {}'.format(self.name, unfinished))
                    else:
                        Logger.debug('{}: stage already passed'.format(self.name))

                # Remove the deleted files from the mongodb document for the analysis
                finished_files = self.doc.files
                for key in deleted:
                    del finished_files[key]
                self.update_doc(files=finished_files)

                Logger.debug('{}: finished file cleanup'.format(self.name))

            email = ('email', self.doc.email, self.doc.owner, 'error',
                     dict(code=self.doc.access_code,
                          analysis='{}-{}'.format(self.doc.workflow_type, self.doc.analysis_type),
                          stage=self.doc.restart_stage,
                          study=self.doc.study_name))
            self.queue.put(email)

        else:
            email = ('email', self.doc.email, self.doc.owner, 'analysis_done',
                     dict(code=self.doc.access_code,
                          analysis='{}-{}'.format(self.doc.workflow_type, self.doc.analysis_type),
                          study=self.doc.study_name))
        self.queue.put(email)
        self.update_doc(restart_stage=-1)  # Indicates analysis finished successfully
        # If testing, no files have been generated
        if not self.testing:
            self.move_user_files()

    def run(self):
        """
        Overrides Process.run()
        This is entry point for the analysis process's execution.
        """
        # Unless all of run completes succesfully exit code should be 1
        exit_code = 1
        try:
            Logger.debug('{} calling run'.format(self.name))
            self.initial_setup()
            self.jobtext.append('{}={};'.format(str(self.run_dir).replace('$', ''), self.path))
            Logger.debug('Finished initial setup')

            Logger.debug('I {} am running analysis'.format(self.name))
            self.run_analysis()

            exit_code = 0  # Tool as completed successfully
        finally:
            # Update the related document that the process as terminated
            self.update_doc(pid=None, is_alive=False, analysis_status='Finished', exit_code=exit_code)


class TestAnalysis(Analysis):
    """
    A class for running tool methods during testing with minimal overhead
    """

    def __init__(self, queue, owner, access_code, study_code, workflow_type, analysis_type, config, testing, runs,
                 run_on_node, analysis=True, restart_stage=0, kill_stage=-1, time=10):
        super().__init__(queue, owner, access_code, study_code, workflow_type, analysis_type, config, testing, runs,
                         run_on_node, analysis=analysis, restart_stage=restart_stage)
        print('Creating test tool with restart stage {} and time {}'.format(restart_stage, time))
        self.time = time

    def run_analysis(self):
        sleep(int(self.time))

    def setup_analysis(self):
        sleep(int(self.doc.analysis_type) / 10)
