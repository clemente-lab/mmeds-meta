from pathlib import Path
from subprocess import run, PIPE
from shutil import copy, rmtree
from time import sleep
from pandas import read_csv

from mmeds.database import Database
from mmeds.config import STORAGE_DIR
from mmeds.mmeds import log
from mmeds.error import AnalysisError


class Tool:
    """ The base class for tools used by mmeds """

    def __init__(self, owner, access_code, atype, config, testing, threads=10, analysis=True):
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
        """
        log('Start analysis')
        self.db = Database('', owner=owner, testing=testing)
        self.access_code = access_code
        files, path = self.db.get_mongo_files(self.access_code)
        self.testing = testing
        self.jobtext = []
        self.owner = owner
        if testing:
            self.num_jobs = 3
        else:
            self.num_jobs = threads
        self.atype = atype.split('-')[1]
        self.analysis = analysis
        self.path, self.run_id, self.files, self.demuxed = self.setup_dir(Path(path))

        # Add the split directory to the MetaData object
        self.add_path('analysis{}'.format(self.run_id), '')
        self.columns = []
        self.config = self.read_config_file(config)

    def __del__(self):
        del self.db

    def setup_dir(self, path):
        """ Setup the directory to run the analysis. """
        log('In setup_dir')
        files = {}
        run_id = 0
        new_dir = path / 'analysis{}'.format(run_id)
        while new_dir.is_dir():
            run_id += 1
            new_dir = path / 'analysis{}'.format(run_id)
        new_dir = new_dir.resolve()
        root_files, root_path = self.db.get_mongo_files(self.access_code)
        if self.analysis:
            run('mkdir {}'.format(new_dir), shell=True, check=True)

            if '.fastq.gz' == Path(root_files['reads']).suffix:
                # Create links to the files
                (new_dir / 'barcodes.fastq.gz').symlink_to(root_files['barcodes'])
                (new_dir / 'sequences.fastq.gz').symlink_to(root_files['reads'])

                # Add the links to the files dict for this analysis
                files['barcodes'] = new_dir / 'barcodes.fastq.gz'
                files['reads'] = new_dir / 'sequences.fastq.gz'

                demuxed = False
            elif '.zip' == Path(root_files['reads']).suffix:
                (new_dir / 'data.zip').symlink_to(root_files['reads'])
                files['data'] = new_dir / 'data.zip'
                demuxed = True
            else:
                demuxed = False
                log('Invalid extension')
                log(root_files['reads'])
                # This should be caught when uploading the data

            (new_dir / 'metadata.tsv').symlink_to(root_files['metadata'])
            files['metadata'] = new_dir / 'metadata.tsv'
            log('Run analysis')
        else:
            run_id -= 1
            new_dir = path / 'analysis{}'.format(run_id)
            if (new_dir / 'summary').is_dir():
                rmtree(new_dir / 'summary')
            string_files = root_files['analysis{}'.format(run_id)]
            files = {key: Path(string_files[key]) for key in string_files.keys()}
            log("Loaded files")
            log(files.keys())
            log("Skip analysis")
            demuxed = False

        log("Analysis directory is {}".format(new_dir))
        return new_dir, str(run_id), files, demuxed

    def unzip(self):
        """ Split the libraries and perform quality analysis. """
        self.add_path('reads', '')
        command = 'unzip {} -d {}'.format(self.files['data'],
                                          self.files['reads'])
        self.jobtext.append(command)

    def read_config_file(self, config_file):
        """ Read the provided config file to determine settings for the analysis. """
        config = {}
        # If no config was provided load the default
        if config_file is None:
            log('Using default config')
            with open(STORAGE_DIR / 'config_file.txt', 'r') as f:
                page = f.read()
        else:
            # Otherwise write the file to the analysis directory for future reference
            log('Using custom config: {}'.format(self.path / 'config_file.txt'))
            with open(self.path / 'config_file.txt', 'w+') as f:
                f.write(config_file)
            # And load the file contents
            page = config_file
        # Parse the config
        lines = page.split('\n')
        for line in lines:
            if line.startswith('#') or line == '':
                continue
            else:
                parts = line.split('\t')
                config[parts[0]] = parts[1]

        # Parse the metadata values to be included in the analysis
        if config['metadata'] == 'all':
            # If it's set to all get all the headers from the mapping file
            with open(self.files['mapping']) as f:
                header = f.readline()
            config['metadata'] = header.strip().split('\t')
        else:
            # Otherwise split the values into a list
            config['metadata'] = config['metadata'].split(',')
        # Ensure #SampleID isn't included
        if '#SampleID' in config['metadata']:
            config['metadata'].remove('#SampleID')
        return config

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(files['mapping'], self.path)
        self.jobtext.append(cmd)

    def get_job_params(self):
        params = {
            'walltime': '6:00',
            'walltime2': '2:00',
            'jobname': '{}/{}-{}-{}'.format(self.path,
                                            self.owner,
                                            self.atype,
                                            self.run_id),
            'nodes': self.num_jobs,
            'memory': 1000,
            'queue': 'expressalloc'
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
            output = run('bjobs', stdout=PIPE).stdout.decode('utf-8').split('\n')
            for job in output:
                # If the job is found set it back to true
                if str(job_id) in job:
                    running = True
            # Wait thirty seconds to check again
            sleep(30)
        return

    def move_user_files(self):
        """ Move all visualization files intended for the user to a set location. """
        try:
            log('Move analysis files into directory')
            self.add_path('visualizations_dir', '')
            if not self.files['visualizations_dir'].is_dir():
                self.files['visualizations_dir'].mkdir()
            for key in self.files.keys():
                f = self.files[key]
                if '.qzv' in str(self.files[key]):
                    new_file = f.name
                    copy(self.files[key], self.files['visualizations_dir'] / new_file)
        except FileNotFoundError as e:
            log(e)
            raise AnalysisError(e.args[1])

    def write_file_locations(self):
        """
        Update the relevant document's metadata and
        create a file_index in the analysis directoy.
        """
        string_files = {str(key): str(self.files[key]) for key in self.files.keys()}
        self.db.update_metadata(self.access_code,
                                'analysis{}'.format(self.run_id),
                                string_files)

        # Create the file index
        with open(self.path / 'file_index.tsv', 'w') as f:
            f.write('{}\t{}\n'.format(self.owner, self.access_code))
            f.write('Key\tPath\n')
            for key in self.files:
                f.write('{}\t{}\n'.format(key, self.files[key]))
        log(self.files.keys())

    def add_path(self, name, extension=''):
        """ Add a file or directory with the full path to self.files. """
        self.files[name] = Path('{}{}'.format(self.path / name, extension))

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        fp = self.files['metadata']
        mdata = read_csv(fp, header=1, skiprows=[2, 3, 4], sep='\t')
        self.columns = list(mdata.columns)

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'

        headers = list(mdata.columns)

        di = headers.index('RawDataID')
        hold = headers[0]
        headers[0] = '#SampleID'
        headers[di] = hold

        di = headers.index('SampleID')
        hold = headers[3]
        headers[3] = 'MmedsSampleID'
        headers[di] = hold

        hold = headers[1]
        di = headers.index('BarcodeSequence')
        headers[1] = 'BarcodeSequence'
        headers[di] = hold

        hold = headers[2]
        di = headers.index('LinkerPrimerSequence')
        headers[2] = 'LinkerPrimerSequence'
        headers[di] = hold

        hold = headers[-1]
        di = headers.index('Description')
        headers[-1] = 'Description'
        headers[di] = hold

        with open(mapping_file, 'w') as f:
            f.write('\t'.join(headers) + '\n')
            for row_index in range(len(mdata)):
                row = []
                for header in headers:
                    if header == '#SampleID':
                        row.append(str(mdata['RawDataID'][row_index]))
                    elif header == 'MmedsSampleID':
                        row.append(str(mdata['SampleID'][row_index]))
                    else:
                        row.append(str(mdata[header][row_index]))
                f.write('\t'.join(row) + '\n')

        # Add the mapping file to the MetaData object
        self.files['mapping'] = mapping_file
