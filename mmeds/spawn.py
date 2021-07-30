import yaml

from time import sleep
from shutil import rmtree
from pathlib import Path
from datetime import datetime, timedelta
from multiprocessing import Queue, Pipe, Lock
from multiprocessing.managers import BaseManager

import mmeds.config as fig
import mmeds.secrets as sec

from mmeds.util import create_local_copy, load_config, send_email
from mmeds.database.database import Database
from mmeds.database.metadata_uploader import MetaDataUploader
from mmeds.database.metadata_adder import MetaDataAdder
from mmeds.error import AnalysisError, MissingUploadError
from mmeds.tools.qiime1 import Qiime1
from mmeds.tools.qiime2 import Qiime2
from mmeds.tools.sparcc import SparCC
from mmeds.tools.lefse import Lefse
from mmeds.tools.picrust1 import PiCRUSt1
from mmeds.tools.tool import TestTool
from mmeds.logging import Logger

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


class Watcher(BaseManager):

    def __init__(self, address=("", sec.WATCHER_PORT), authkey=sec.AUTH_KEY):
        """
        Initialize an instance of the Watcher class. It inherits from multiprocessing.Process
        =====================================================================================
        :queue: A multiprocessing.Queue object. When the Watcher process needs to start some other process
            the necessary information will be added to this queue.
        :testing: A boolean. If true run in testing configuration, otherwise run in deployment configuration.
        """
        # import pudb; pudb.set_trace()
        super().__init__(address, authkey)
        self.testing = fig.TESTING
        self.count = 0
        self.processes = []
        self.running_processes = []
        self.started = []
        self.running_on_node = set()
        self.logger = Logger
        self.current_upload = None
        self.checked_stats = None
        self.cleaned_temp = None

        queue = Queue()
        self.register('get_queue', callable=lambda: queue)
        pipe_ends = Pipe()
        self.pipe = pipe_ends[0]
        self.register('get_pipe', callable=lambda: pipe_ends[1])
        self.db_lock = Lock()
        self.register('get_db_lock', callable=lambda: self.db_lock)

    def start(self):
        super().start()
        self.set_queue()
        self.run()

    def set_queue(self):
        self.q = self.get_queue()

    def print_queue(self):
        print('My queue is {}'.format(self.q))
        while True:
            print(self.q.get())
            sleep(1)

    def spawn_analysis(self, tool_type, analysis_type, user, parent_code,
                       config_file, testing, run_on_node, kill_stage=-1):
        """ Start running the analysis in a new process """
        # Create access code for this analysis
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

    def check_upload(self):
        """ Check the status of the current upload. Release the lock if it's finished """
        # Check that there isn't another process currently uploading
        if self.current_upload is None or not self.current_upload.is_alive():
            self.current_upload = None
            try:
                self.db_lock.release()
            except ValueError:
                pass

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


    def clean_temp_folders(self):
        """ Clean out temp folders older than a day, once every day."""
        # Check if a day has passed since we cleaned out temp folders.

        if self.cleaned_temp is None or datetime.utcnow() - self.cleaned_temp > timedelta(days=1):
            # import pudb; pudb.set_trace()
            temp_sub_dirs = (Path(fig.DATABASE_DIR) / 'temp_dir').glob('*')
            for temp_sub_dir in temp_sub_dirs:
                # Check if any temp folder is more than a day old.
                # TODO: Note that if any uploads take longer than a day this could cause a problem.
                if self.cleaned_temp is None or \
                        datetime.utcnow() - datetime.fromtimestamp(temp_sub_dir.stat().st_mtime) > timedelta(days=1):
                    rmtree(temp_sub_dir)

            self.cleaned_temp = datetime.utcnow()


    def update_stats(self):
        """ Update the mmeds stats to their most recent values """

        # Update when the watcher starts and every five minutes thereafter
        if self.checked_stats is None or (datetime.utcnow() - self.checked_stats) > timedelta(minutes=5):
            # Get stats for MMEDs server
            with Database(testing=self.testing) as db:
                args = {
                    'study_count': len(db.get_all_studies()),
                    'analysis_count': len(db.get_all_analyses()),
                    'user_count': len(db.get_all_usernames()),
                    'query_count': 42,
                }
            # If there's already a file remove it
            if fig.STAT_FILE.exists():
                fig.STAT_FILE.unlink()
            # Write the new stats
            with open(fig.STAT_FILE, 'w') as f:
                yaml.safe_dump(args, f)
            self.checked_stats = datetime.utcnow()

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

    def handle_upload(self, process):
        """
        :process: A n-tuple containing information on what process to spawn.
        ====================================================================
        Handles the creation of uploader processes
        """
        self.check_upload()

        # If there is nothing uploading currently start the new upload process
        if self.current_upload is None:
            # Check what type of upload this is
            if 'ids' in process[0]:
                (ptype, owner, access_code, aliquot_table, id_type, generate_id) = process
                p = MetaDataAdder(owner, access_code, aliquot_table, id_type, generate_id, self.testing)
            else:
                (ptype, study_name, subject_metadata, subject_type, specimen_metadata,
                 username, reads_type, barcodes_type, datafiles, temporary, public) = process
                # Start a process to handle loading the data
                p = MetaDataUploader(subject_metadata, subject_type, specimen_metadata, username, 'qiime', reads_type,
                                     barcodes_type, study_name, temporary, datafiles, public, self.testing)
                self.db_lock.acquire()
            p.start()
            self.add_process(ptype, p.access_code)
            with Database(testing=self.testing) as db:
                doc = db.get_doc(p.access_code, False)
            self.pipe.send(doc.get_info())
            # Keep track of this new process
            self.started.append(p.access_code)
            self.current_upload = p
            if self.testing:
                p.join()
        else:
            # If there is another upload return the process info to the queue
            self.q.put(process)

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
        # Continue until it's parent process is killed
        while True:
            self.update_stats()
            self.clean_temp_folders()
            self.check_processes()
            self.check_upload()
            self.write_running_processes()
            self.log_processes()
            self.count += 1
            # If there is nothing in the process queue, sleep
            if self.q.empty():
                if self.count == 20:
                    self.count = 0
                sleep(3)
            else:
                # Otherwise get the queued item
                process = self.q.get()
                self.logger.error("got something {}".format(process))
                print("Got something {}".format(process))
                self.logger.error('Got process requirements')
                self.logger.error(process)
                # Whenever it's acceptable to move to Python 3.10 this needs to be turned into a switch statement
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
                elif 'upload' in process[0]:
                    Logger.error("Got an upload, processing")
                    self.handle_upload(process)
                elif process[0] == 'email':
                    self.logger.error('Sending email')
                    ptype, toaddr, user, message, kwargs = process
                    # If the analysis that finished was running directly on the node remove it from the set
                    if kwargs.get('access_code') in self.running_on_node:
                        self.running_on_node.remove(kwargs.get('access_code'))

                    send_email(toaddr, user, message, self.testing, **kwargs)
                elif process[0] == 'connected':
                    self.logger.error('Someone connected')
