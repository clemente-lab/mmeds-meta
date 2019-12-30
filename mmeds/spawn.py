from time import sleep
from multiprocessing import Process
from shutil import rmtree
from pathlib import Path
from datetime import datetime

import mmeds.config as fig
import yaml

from mmeds.util import (send_email, create_local_copy, debug_log, load_config, error_log)
from mmeds.database import MetaDataUploader, Database
from mmeds.error import AnalysisError
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2
from mmeds.sparcc import SparCC
from mmeds.tool import TestTool


def test(time):
    """ Simple function for analysis called during testing """
    sleep(time)


def spawn_analysis(tool_type, analysis_type, user, access_code, config_file, testing, kill_stage=-1):
    """ Start running the analysis in a new process """
    # Load the config for this analysis
    with Database('.', owner=user, testing=testing) as db:
        files, path = db.get_mongo_files(access_code)
    config = load_config(config_file, files['metadata'])

    if 'qiime1' in atype:
        tool = Qiime1(user, access_code, tool_type, analysis_type, config, testing, kill_stage=kill_stage)
    elif 'qiime2' in atype:
        tool = Qiime2(user, access_code, tool_type, analysis_type, config, testing, kill_stage=kill_stage)
    elif 'sparcc' in atype:
        tool = SparCC(user, access_code, tool_type, analysis_type, config, testing, kill_stage=kill_stage)
    elif 'test' in atype:
        debug_log('test analysis')
        time = float(atype.split('-')[-1])
        tool = TestTool(user, access_code, atype, config, testing, time=time)
    else:
        raise AnalysisError('atype didnt match any')

    send_email(tool.doc.email, user, message='analysis_start', code=access_code,
               testing=testing, study=tool.doc.study_name)
    return tool


def handle_modify_data(access_code, myData, user, data_type, testing):
    with Database(owner=user, testing=testing) as db:
        # Create a copy of the Data file
        files, path = db.get_mongo_files(access_code=access_code)
        data_copy = create_local_copy(myData[1], myData[0], path=path)
        db.modify_data(data_copy, access_code, data_type)


def restart_analysis(user, code, restart_stage, testing, kill_stage=-1, run_analysis=True):
    """ Restart the specified analysis. """
    with Database('.', owner=user, testing=testing) as db:
        ad = db.get_doc(code)

    # Create an entire new directory if restarting from the beginning
    if restart_stage < 1:
        code = ad.study_code
        if Path(ad.path).exists():
            rmtree(ad.path)

    # Create the appropriate tool
    if 'qiime1' in ad.doc_type:
        tool = Qiime1(owner=ad.owner, access_code=code, atype=ad.doc_type, config=ad.config,
                      testing=testing, analysis=run_analysis, restart_stage=restart_stage)
    elif 'qiime2' in ad.doc_type:
        tool = Qiime2(owner=ad.owner, access_code=code, atype=ad.doc_type, config=ad.config,
                      testing=testing, analysis=run_analysis, restart_stage=restart_stage, kill_stage=kill_stage)
    elif 'test' in ad.doc_type:
        debug_log('test analysis')
        tool = TestTool(user, code, ad.doc_type, ad.config, testing, time=20)
    else:
        raise AnalysisError('atype didnt match any')
    return tool


def spawn_sub_analysis(user, code, category, value, testing):
    """ Spawn a new sub analysis from a previous analysis. """
    tool = restart_analysis(user, code, 1, testing)
    child = tool.create_sub_analysis(category, value)
    return child


def killall(processes):
    for p in processes:
        p.kill()


class Watcher(Process):

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
        super().__init__()

    def add_process(self, ptype, process):
        """ Add an analysis process to the list of processes. """
        error_log('Add process {}, type: {}'.format(process, ptype))
        self.running_processes.append(process)
        self.write_running_processes()

    def check_processes(self):
        still_running = []
        # For each type of process 'upload', 'analysis', 'etc'
        # Check each process is still alive
        while self.running_processes:
            process = self.running_processes.pop()
            if process.is_alive():
                still_running.append(process)
            else:
                self.processes.append(process)
                # Send the exitcode of the process
                self.pipe.send(process.exitcode)
        for process in still_running:
            self.running_processes.append(process)

    def write_running_processes(self):
        writeable = [process.get_info() for process in self.running_processes]
        with open(fig.CURRENT_PROCESSES, 'w+') as f:
            yaml.dump(writeable, f)

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
            with open(current_log, 'r') as f:
                finished += yaml.safe_load(f)

        with open(current_log, 'w+') as f:
            yaml.dump(finished, f)
        # Remove logged processes so they aren't recorded twice
        self.processes.clear()

    def get_exit_codes(self, ptype):
        """ Get exit codes for processes that have finished. """
        return [process.exit_code for process in self.processes[ptype]]

    def any_running(self, ptype):
        """ Returns true if there is a process running """
        return bool(self.running_processes['ptype'])

    def get_processes(self):
        return self.running_processes, self.processes

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
                # Retrieve the info
                debug_log('Got process from queue')
                debug_log(process)

                # If it's an analysis
                if process[0] == 'analysis':
                    ptype, user, access_code, tool_type, analysis_type, config, kill_stage = process
                    p = spawn_analysis(tool_type, analysis_type, user, access_code, config, self.testing, kill_stage)
                    # Start the analysis running
                    p.start()
                    self.pipe.send(p.get_info())
                    # Add it to the list of analysis processes
                    self.add_process(ptype, p)
                # IF it's a restart of an analysis
                elif process[0] == 'restart':
                    ptype, user, analysis_code, restart_stage, kill_stage = process
                    p = restart_analysis(user, analysis_code, restart_stage,
                                         self.testing, kill_stage=kill_stage, run_analysis=True)
                    # Start the analysis running
                    p.start()
                    self.pipe.send(p.get_info())
                    # Add it to the list of analysis processes
                    self.add_process(ptype, p)
                # If it's an upload
                elif process[0] == 'upload':
                    # Check that there isn't another process currently uploading
                    if current_upload is not None and current_upload.is_alive():
                        # If there is another upload return the process info to the queue
                        self.q.put(process)
                        sleep(3)
                    else:
                        current_upload = None

                    # If there is nothing uploading currently start the new upload process
                    if current_upload is None:
                        (ptype, study_name, subject_metadata, specimen_metadata,
                         username, reads_type, barcodes_type, datafiles, temporary, public) = process
                        # Start a process to handle loading the data
                        p = MetaDataUploader(subject_metadata, specimen_metadata, username, 'qiime', reads_type,
                                             barcodes_type, study_name, temporary, datafiles, public, self.testing)
                        p.start()
                        self.add_process('upload', p)
                        self.pipe.send(p.get_info())
                        self.started.append(p)
                        current_upload = p
                        if self.testing:
                            p.join()
