from time import sleep
from multiprocessing import Process
from shutil import rmtree
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from mmeds.util import (send_email, create_local_copy, log, load_config,
                        read_processes, write_processes, error_log)
from mmeds.database import MetaDataUploader, Database
from mmeds.error import AnalysisError
from mmeds.qiime1 import Qiime1
from mmeds.qiime2 import Qiime2


def test(time):
    """ Simple function for analysis called during testing """
    sleep(time)


def spawn_analysis(atype, user, access_code, config_file, testing):
    """ Start running the analysis in a new process """
    # Load the config for this analysis
    with Database('.', owner=user, testing=testing) as db:
        files, path = db.get_mongo_files(access_code)

    if isinstance(config_file, str):
        log('load path config {}'.format(config_file))
        config = load_config(config_file, files['metadata'])
    elif config_file is None or config_file.file is None:
        log('load default config')
        config = load_config(None, files['metadata'])
    else:
        log('load passed config')
        config = load_config(config_file.file.read().decode('utf-8'), files['metadata'])

    if 'qiime1' in atype:
        tool = Qiime1(user, access_code, atype, config, testing)
    elif 'qiime2' in atype:
        tool = Qiime2(user, access_code, atype, config, testing)
    elif 'test' in atype:
        log('test analysis')
        time = float(atype.split('-')[-1])
        tool = Process(target=test, args=(time,))
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


def spawn_data_upload(subject_metadata, specimen_metadata, username, reads_type,
                      study_name, temporary, public, testing, *datafiles):
    """
    Thread that handles the upload of large data files.
    ===================================================
    :metadata_copy: A string. Location of the metadata.
    :reads: A tuple. First element is the name of the reads/data file,
    the second is a file type io object
    :barcodes: A tuple. First element is the name of the barcodes file,
    the second is a file type io object
    :username: A string. Name of the user that is uploading the files.
    :testing: True if the server is running locally.
    :datafiles: A list of datafiles to be uploaded
    """
    # Upload the combined file to the database
    p = MetaDataUploader(subject_metadata=subject_metadata, specimen_metadata=specimen_metadata,
                         study_type='qiime', reads_type=reads_type, owner=username, study_name=study_name,
                         temporary=temporary, testing=testing, public=public, data_files=datafiles)
    return p


def restart_analysis(user, code, restart_stage, testing, kill_stage=-1, run_analysis=True):
    """ Restart the specified analysis. """
    with Database('.', owner=user, testing=testing) as db:
        ad = db.get_analysis(code)

    # Create an entire new directory if restarting from the beginning
    if restart_stage < 1:
        code = ad.study_code
        if Path(ad.path).exists():
            rmtree(ad.path)

    # Create the appropriate tool
    if 'qiime1' in ad.analysis_type:
        tool = Qiime1(owner=ad.owner, access_code=code, atype=ad.analysis_type, config=ad.config,
                      testing=testing, analysis=run_analysis, restart_stage=restart_stage)
    elif 'qiime2' in ad.analysis_type:
        tool = Qiime2(owner=ad.owner, access_code=code, atype=ad.analysis_type, config=ad.config,
                      testing=testing, analysis=run_analysis, restart_stage=restart_stage, kill_stage=kill_stage)
    return tool


def spawn_sub_analysis(user, code, category, value, testing):
    """ Spawn a new sub analysis from a previous analysis. """
    tool = restart_analysis(user, code, 1, testing)
    child = tool.create_child(category, value)
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
        self.processes = [] # read_processes()
        self.running_processes = []
        self.pipe = pipe
        self.parent_pid = parent_pid
        self.started = []
        super().__init__()
        print('I am watch {}'.format(self.name))

    def add_process(self, ptype, process):
        """ Add an analysis process to the list of processes. """
        error_log('Add process {}, type: {}'.format(process, ptype))
        #self.processes[ptype].append(process)
        self.running_processes.append(process)

        print('dict {}: {}'.format(id(self.running_processes), self.running_processes))
        #write_processes(self.processes)

    def check_processes(self):
        still_running = []
        # For each type of process 'upload', 'analysis', 'etc'
        # Check each process is still alive
        while self.running_processes:
            process = self.running_processes.pop()
            if process.is_alive():
                print('process {} alive'.format(process.name))
                still_running.append(process)
            else:
                print('process {} died'.format(process.name))
                self.processes.append(process)
                # Send the exitcode of the process
                self.pipe.send(process.exitcode)
        for process in still_running:
            self.running_processes.append(process)

    def get_exit_codes(self, ptype):
        """ Get exit codes for processes that have finished. """
        return [process.exit_code for process in self.processes[ptype]]

    def any_running(self, ptype):
        """ Returns true if there is a process running """
        return bool(self.running_processes['ptype'])

    def get_processes(self):
        print('running {}'.format(self.running_processes))
        print('done {}'.format(self.processes))
        return self.running_processes, self.processes

    def run(self):
        """ The loop to run when a Watcher is started """
        current_upload = None
        print('I am the watcher {}'.format(id(self)))
        # Continue until it's parent process is killed
        while True:
            self.check_processes()
            #write_processes(self.processes)
            # If there is nothing in the process queue, sleep
            if self.q.empty():
                sleep(1)
            else:
                # Otherwise get the queued item
                process = self.q.get()
                # Retrieve the info
                log('Got process from queue')
                log(process)

                # If it's an analysis
                if process[0] == 'analysis':
                    ptype, user, access_code, tool, config = process
                    # Start the analysis running
                    p = spawn_analysis(tool, user, access_code, config, self.testing)
                    p.start()
                    # Add it to the list of analysis processes
                    self.add_process(ptype, p)
                # If it's an upload
                elif process[0] == 'upload':
                    # Check that there isn't another process currently uploading
                    if current_upload is not None and current_upload.is_alive():
                        # If there is another upload return the process info to the queue
                        self.q.put(process)
                        sleep(10)
                    else:
                        current_upload = None

                    # If there is nothing uploading currently start the new upload process
                    if current_upload is None:
                        (ptype, study_name, subject_metadata, specimen_metadata,
                         username, reads_type, datafiles, temporary, public) = process
                        # Start a process to handle loading the data
                        p = spawn_data_upload(subject_metadata, specimen_metadata, username,
                                              reads_type, study_name, temporary, public, self.testing,
                                              # Unpack the list so the files are taken as a tuple
                                              *datafiles)
                        p.start()
                        self.add_process('upload', p)
                        self.started.append(p)
                        current_upload = p
                        if self.testing:
                            p.join()
