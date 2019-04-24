from pathlib import Path
from subprocess import run
from shutil import copy
from time import sleep
from copy import deepcopy

from mmeds.database import Database
from mmeds.util import log, create_qiime_from_mmeds, copy_metadata, load_metadata, write_df_as_mmeds
from mmeds.error import AnalysisError


class Tool:
    """ The base class for tools used by mmeds """

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
        """
        log('Start analysis')
        self.access_code = access_code
        self.testing = testing
        self.jobtext = []
        self.owner = owner
        self.atype = atype.split('-')[1]
        self.tool = atype.split('-')[0]
        self.analysis = analysis
        self.config = config
        self.columns = []

        with Database(owner=self.owner, testing=self.testing) as db:
            files, path = db.get_mongo_files(self.access_code)
        if testing:
            self.num_jobs = 2
        else:
            self.num_jobs = threads
        self.path, self.run_id, self.files, self.data_type = self.setup_dir(Path(path))
        self.run_dir = Path('$RUN_{}'.format(self.run_id))
        self.add_path('analysis{}'.format(self.run_id), '')
        self.write_config()
        self.create_qiime_mapping_file()
        self.children = []
        self.is_child = False

    def get_file(self, key):
        """ Get the path to the file stored under 'key' relative to the run dir """
        return self.run_dir / self.files[key].relative_to(self.path)

    def spawn_child_tool(self, category, value):
        """
        Create a child analysis process using only samples that have a particular value
        in a particular metadata column. Handles creating the analysis directory and such
        ===============================
        :category: The column of the metadata to filter by
        :value: The value that :column: must match for a sample to be included
        """
        child = deepcopy(self)

        child.path = self.path / 'child_{}_{}'.format(category[1], value)
        child.path.mkdir()
        child.files = {
            'metadata': child.path / 'metadata.tsv'
        }
        for parent_file in ['for_reads', 'rev_reads', 'barcodes']:
            if self.files.get(parent_file) is not None:
                child_file = child.path / self.files.get(parent_file).name
                child_file.symlink_to(self.files.get(parent_file))
                child.files[parent_file] = child_file

        # Filter the metadata and write the new file to the childs directory
        mdf = load_metadata(self.files['metadata'])
        new_mdf = mdf.loc[mdf[category] == value]
        write_df_as_mmeds(new_mdf, child.files['metadata'])

        # Update child's vars
        child.add_path('analysis{}/child_{}_{}/'.format(child.run_id, category[1], value), '')
        child.run_dir = Path('$RUN_{}_{}_{}'.format(child.run_id, category[1], value))
        child.jobtext.append('{}={};'.format(str(child.run_dir).replace('$', ''), child.path))
        child.write_config()
        child.create_qiime_mapping_file()
        child.is_child = True

        # Filter the config for the metadata category selected for this sub-analysis
        child.config['metadata'] = [cat for cat in self.config['metadata'] if not cat == category[1]]
        return child

    def setup_dir(self, path):
        """ Setup the directory to run the analysis. """
        log('In setup_dir')
        files = {}
        run_id = 0
        # Create a new directory to perform the analysis in
        new_dir = path / 'analysis{}'.format(run_id)
        while new_dir.is_dir():
            run_id += 1
            new_dir = path / 'analysis{}'.format(run_id)

        new_dir = new_dir.resolve()
        with Database(owner=self.owner, testing=self.testing) as db:
            metadata = db.get_metadata(self.access_code)
        new_dir.mkdir()
        # Handle demuxed sequences
        if Path(metadata.files['for_reads']).suffix in ['.zip', '.tar']:
            (new_dir / 'data.zip').symlink_to(metadata.files['for_reads'])
            files['data'] = new_dir / 'data.zip'
            data_type = metadata.reads_type + '_demuxed'
        # Handle all sequences in one file
        else:
            # Create links to the files
            (new_dir / 'barcodes.fastq.gz').symlink_to(metadata.files['barcodes'])
            (new_dir / 'for_reads.fastq.gz').symlink_to(metadata.files['for_reads'])

            # Add the links to the files dict for this analysis
            files['barcodes'] = new_dir / 'barcodes.fastq.gz'
            files['for_reads'] = new_dir / 'for_reads.fastq.gz'

            # Handle paired end sequences
            if metadata.reads_type == 'paired_end':
                # Create links to the files
                (new_dir / 'rev_reads.fastq.gz').symlink_to(metadata.files['rev_reads'])

                # Add the links to the files dict for this analysis
                files['rev_reads'] = new_dir / 'rev_reads.fastq.gz'
            data_type = metadata.reads_type

        copy_metadata(metadata.files['metadata'], new_dir / 'metadata.tsv')
        files['metadata'] = new_dir / 'metadata.tsv'
        log("Analysis directory is {}. Run.".format(new_dir))
        return new_dir, str(run_id), files, data_type

    def write_config(self):
        """ Write out the config file being used to the working directory. """
        config_text = []
        for (key, value) in self.config.items():
            # Don't write values that are generated on loading
            if key in ['Together', 'Separate', 'metadata_continuous', 'taxa_levels_all', 'metadata_all']:
                continue
            # If the value was initially 'all', write that
            elif key in ['taxa_levels', 'metadata']:
                if self.config['{}_all'.format(key)]:
                    config_text.append('{}\t{}'.format(key, 'all'))
                # Write lists as comma seperated strings
                else:
                    config_text.append('{}\t{}'.format(key, ','.join(list(map(str, value)))))
            else:
                config_text.append('{}\t{}'.format(key, value))
        (self.path / 'config_file.txt').write_text('\n'.join(config_text))

    def unzip(self):
        """ Split the libraries and perform quality analysis. """
        self.add_path('for_reads', '')
        command = 'unzip {} -d {}'.format(self.get_file('data'),
                                          self.get_file('for_reads'))
        self.jobtext.append(command)

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        with Database(owner=self.owner, testing=self.testing) as db:
            files, path = db.get_mongo_files(self.access_code)
        cmd = 'validate_mapping_file.py -s -m {} -o {};'.format(files['mapping'], self.path)
        self.jobtext.append(cmd)

    def get_job_params(self):
        params = {
            'walltime': '6:00',
            'walltime2': '2:00',
            'jobname': '{}-{}-{}'.format(self.owner,
                                         self.atype,
                                         self.run_id),
            'path': self.path,
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

        with Database(owner=self.owner, testing=self.testing) as db:
            db.update_metadata(self.access_code,
                               'analysis{}'.format(self.run_id),
                               string_files)

        # Create the file index
        with open(self.path / 'file_index.tsv', 'w') as f:
            f.write('{}\t{}\n'.format(self.owner, self.access_code))
            f.write('Key\tPath\n')
            for key in self.files:
                f.write('{}\t{}\n'.format(key, self.files[key]))
        log(self.files.keys())

    def add_path(self, name, extension='', key=None):
        """ Add a file or directory with the full path to self.files. """
        if key:
            self.files[key] = Path('{}{}'.format(self.path / name, extension))
        else:
            self.files[name] = Path('{}{}'.format(self.path / name, extension))

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        mmeds_file = self.files['metadata']

        # Create the Qiime mapping file
        qiime_file = self.path / 'qiime_mapping_file.tsv'

        self.columns = create_qiime_from_mmeds(mmeds_file, qiime_file, self.tool)

        # Add the mapping file to the MetaData object
        self.files['mapping'] = qiime_file

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
            db.update_metadata(self.access_code,
                               'analysis{}_summary'.format(self.run_id),
                               str(self.path / 'summary/analysis.pdf'))
            db.update_metadata(self.access_code,
                               'analysis{}_summary_dir'.format(self.run_id),
                               str(self.path / 'summary'))
