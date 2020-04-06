from time import sleep
from multiprocessing import Process, current_process
from shutil import rmtree
from pathlib import Path
from datetime import datetime

import mmeds.config as fig
import yaml

from mmeds.util import create_local_copy, load_config, send_email
from mmeds.database import MetaDataUploader, Database
from mmeds.error import AnalysisError, MissingUploadError
from mmeds.tools.qiime1 import Qiime1
from mmeds.tools.qiime2 import Qiime2
from mmeds.tools.sparcc import SparCC
from mmeds.tools.lefse import Lefse
from mmeds.tools.picrust1 import PiCRUSt1
from mmeds.tools.tool import TestTool
from mmeds.log import MMEDSLog

TOOLS = {
    'qiime1': Qiime1,
    'qiime2': Qiime2,
    'sparcc': SparCC,
    'lefse': Lefse,
    'picrust1': PiCRUSt1,
    'test': TestTool
}


def handle_modify_data(access_code, myData, user, data_type, testing):
    with Database(owner=user, testing=testing) as db:
        # Create a copy of the Data file
        files, path = db.get_mongo_files(access_code=access_code)
        data_copy = create_local_copy(myData[1], myData[0], path=path)
        db.modify_data(data_copy, access_code, data_type)


def killall(processes):
    for p in processes:
        p.kill()


class Watcher(Process):

    logger = MMEDSLog('spawn-debug').logger

    def __init__(self, queue, pipe, parent_pid, testing=False):
        """
        Initialize an instance of the Watcher class. It inherits from multiprocessing.Process
        =====================================================================================
        :queue: A multiprocessing.Queue object. When the Watcher process needs to start some other process
            the necessary information will be added to this queue.
        :testing: A boolean. If true run in testing configuration, otherwise run in deployment configuration.
        """
        self.testing = testing
        self.q = queue
        self.processes = []
        self.running_processes = []
        self.pipe = pipe
        self.parent_pid = parent_pid
        self.started = []
        self.running_on_node = set()
        super().__init__()

    def spawn_analysis(self, tool_type, analysis_type, user, parent_code,
                       config_file, testing, run_on_node, kill_stage=-1):
        """ Start running the analysis in a new process """
        # Load the config for this analysis
        with Database('.', owner=user, testing=testing) as db:
            files, path = db.get_mongo_files(parent_code)
            access_code = db.create_access_code()
        config = load_config(config_file, files['metadata'])
        try:
            tool = TOOLS[tool_type](self.q, user, access_code, parent_code, tool_type,
                                    analysis_type, config, testing, run_on_node,
                                    kill_stage=kill_stage)
        except KeyError:
            raise AnalysisError('Tool type did not match any')
        return tool

    def restart_analysis(self, user, analysis_code, restart_stage, testing,
                         run_on_node, kill_stage=-1, run_analysis=True):
        """ Restart the specified analysis. """
        with Database('.', owner=user, testing=testing) as db:
            ad = db.get_doc(analysis_code)
        ad.modify(is_alive=True, exit_code=1)

        # TODO remove, handle in Tool
        # Create an entire new directory if restarting from the beginning
        if restart_stage < 1:
            if Path(ad.path).exists():
                rmtree(ad.path)
        # Create the appropriate tool
        try:
            tool = TOOLS[ad.tool_type](self.q, ad.owner, analysis_code, ad.study_code, ad.tool_type,
                                       ad.analysis_type, ad.config, testing, run_on_node,
                                       analysis=run_analysis, restart_stage=restart_stage, kill_stage=kill_stage)
        except KeyError:
            raise AnalysisError('Tool type did not match any')
        return tool

    def spawn_sub_analysis(self, user, code, category, value, testing):
        """ Spawn a new sub analysis from a previous analysis. """
        tool = self.restart_analysis(user, code, 1, testing)
        child = tool.create_sub_analysis(category, value)
        return child

    def add_process(self, ptype, process_code):
        """ Add a process to the list of currently running processes. """
        self.running_processes.append(process_code)
        self.write_running_processes()

    def check_processes(self):
        """
        Updates the list of currently running processes. It does this by checking
        the mongo documents for he processes. Completed processes are removed from
        current_processes and written to the completed process log
        """
        still_running = []
        with Database(testing=self.testing) as db:
            # For each type of process 'upload', 'analysis', 'etc'
            # Check each process is still alive
            while self.running_processes:
                process_code = self.running_processes.pop()
                process_doc = None
                while process_doc is None:
                    try:
                        process_doc = db.get_doc(process_code, False)
                    except MissingUploadError:
                        sleep(1)
                # Record the processes that are still alive
                if process_doc.is_alive:
                    still_running.append(process_code)
                else:
                    self.processes.append(process_doc)
                    # Send the exitcode of the process
                    self.pipe.send(process_doc.exit_code)
        for process in still_running:
            self.running_processes.append(process)

    def write_running_processes(self):
        """
        Writes the currently running processes to the process log
        """
        writeable = []
        for process_code in self.running_processes:
            try:
                with Database(testing=self.testing) as db:
                    doc = db.get_doc(process_code, False)
                info = doc.get_info()
                writeable.append(info)
            # If the upload doesn't exist yet, just proceed
            except MissingUploadError:
                continue
        with open(fig.CURRENT_PROCESSES, 'w+') as f:
            yaml.dump(sorted(writeable, key=lambda x: x['created']), f)

    def log_processes(self):
        """
        Function for writing the access codes to all processes tracked by the server upon server exit.
        Part of the functionality for continuing unfinished analyses on server restart.
        ===============================================================================
        :processes: A dictionary of processes
        """
        finished = [process.get_info() for process in self.processes]

        # There is a seperate log of processes for each day
        current_log = fig.PROCESS_LOG_DIR / (datetime.now().strftime('%Y%m%d') + '.yaml')
        if current_log.exists():
            try:
                finished += yaml.safe_load(current_log.read_text())
            # TODO Figure out why this is happening
            except TypeError:
                self.logger.error('Error loading process log {}. Removing corrupted log.'.format(current_log))
                current_log.unlink()

        # Only create the file if there are processes to log
        if finished:
            with open(current_log, 'w+') as f:
                yaml.dump(finished, f)
        # Remove logged processes so they aren't recorded twice
        self.processes.clear()

    def update_stats(self):
        """ Update the mmeds stats to their most recent values """
        # Get stats for MMEDs server
        with Database(testing=self.testing) as db:
            args = {
                'study_count': len(db.get_all_studies()),
                'analysis_count': len(db.get_all_analyses()),
                'user_count': len(db.get_all_usernames()),
                'query_count': 42,
            }
        with open(fig.STAT_FILE, 'w+') as f:
            yaml.safe_dump(args, f)

    def any_running(self, ptype):
        """ Returns true if there is a process running """
        return bool(self.running_processes['ptype'])

    def get_processes(self):
        return self.running_processes, self.processes

    def handle_analysis(self, process):
        """
        :process: A n-tuple containing information on what process to spawn.
        ====================================================================
        Handles the creation of analysis processes
        """
        ptype, user, access_code, tool_type, analysis_type, config, kill_stage, run_on_node = process

        # If running directly on the server node
        if run_on_node:
            # Inform the user if there are too many processes already running
            if len(self.running_on_node) > 3:
                with Database(testing=self.testing) as db:
                    toaddr = db.get_email(user)
                send_email(toaddr, user, 'too_many_on_node', self.testing, analysis=tool_type)
                self.pipe.send('Analysis Not Started')
                return

        # Otherwise continue
        p = self.spawn_analysis(tool_type, analysis_type, user, access_code,
                                config, self.testing, kill_stage, run_on_node)
        # Start the analysis running
        p.start()
        sleep(1)
        with Database(testing=self.testing, owner=user) as db:
            doc = db.get_doc(p.access_code)

        # Store the access code
        if run_on_node:
            self.running_on_node.add(p.access_code)
        self.pipe.send(doc.get_info())
        # Add it to the list of analysis processes
        self.add_process(ptype, p.access_code)

    def handle_upload(self, process, current_upload):
        """
        :process: A n-tuple containing information on what process to spawn.
        ====================================================================
        Handles the creation of uploader processes
        """
        # Check that there isn't another process currently uploading
        if current_upload is not None and current_upload.is_alive():
            # If there is another upload return the process info to the queue
            self.q.put(process)
            sleep(3)
        else:
            current_upload = None

        # If there is nothing uploading currently start the new upload process
        if current_upload is None:
            (ptype, study_name, subject_metadata, subject_type, specimen_metadata,
             username, reads_type, barcodes_type, datafiles, temporary, public) = process
            # Start a process to handle loading the data
            p = MetaDataUploader(subject_metadata, subject_type, specimen_metadata, username, 'qiime', reads_type,
                                 barcodes_type, study_name, temporary, datafiles, public, self.testing)
            p.start()
            self.add_process('upload', p.access_code)

            with Database(testing=self.testing) as db:
                doc = db.get_doc(p.access_code, False)
            self.pipe.send(doc.get_info())
            self.started.append(p.access_code)
            current_upload = p
            if self.testing:
                p.join()
        return current_upload

    def handle_restart(self, process):
        """
        :process: A n-tuple containing information on what process to spawn.
        ====================================================================
        Handles creating new processes to restart previous analyses.
        """
        ptype, user, analysis_code, run_on_node, restart_stage, kill_stage = process
        p = self.restart_analysis(user, analysis_code, restart_stage, self.testing,
                                  run_on_node, kill_stage=kill_stage, run_analysis=True)
        # Start the analysis running
        p.start()
        sleep(1)
        with Database(testing=self.testing, owner=user) as db:
            doc = db.get_doc(p.access_code)
        self.pipe.send(doc.get_info())
        # Add it to the list of analysis processes
        self.add_process(ptype, p.access_code)

    def run(self):
        """ The loop to run when a Watcher is started """
        current_upload = None
        # Continue until it's parent process is killed
        while True:
            self.check_processes()
            self.write_running_processes()
            self.log_processes()

            # If there is nothing in the process queue, sleep
            if self.q.empty():
                sleep(3)
            else:
                # Otherwise get the queued item
                process = self.q.get()
                self.logger.error('Got process requirements')
                self.logger.error(process)
                # If the watcher needs to shut down
                if process == 'terminate':
                    self.logger.error('Terminating')
                    # Kill all the processes currently running
                    for process in self.processes:
                        self.logger.error('Killing process {}'.format(process))
                        while process.is_alive():
                            process.kill()
                    # Notify other processes the watcher is exiting
                    self.pipe.send('Watcher exiting')
                    exit()
                # If it's an analysis
                elif process[0] == 'analysis':
                    self.handle_analysis(process)
                # If it's a restart of an analysis
                elif process[0] == 'restart':
                    self.handle_restart(process)
                # If it's an upload
                elif process[0] == 'upload':
                    current_upload = self.handle_upload(process, current_upload)
                elif process[0] == 'email':
                    self.logger.error('Sending email')
                    ptype, toaddr, user, message, kwargs = process
                    # If the analysis that finished was running directly on the node remove it from the set
                    if kwargs.get('access_code') in self.running_on_node:
                        self.running_on_node.remove(kwargs.get('access_code'))

                    send_email(toaddr, user, message, self.testing, **kwargs)
