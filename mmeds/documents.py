import mongoengine as men
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from mmeds.config import get_salt
from mmeds.util import copy_metadata, log
from ppretty import ppretty


class StudyDoc(men.Document):
    created = men.DateTimeField()
    last_accessed = men.DateTimeField()
    testing = men.BooleanField(required=True)
    study_type = men.StringField(max_length=45, required=True)
    reads_type = men.StringField(max_length=45, required=True)
    study = men.StringField(max_length=45, required=True)
    access_code = men.StringField(max_length=50, required=True)
    owner = men.StringField(max_length=100, required=True)
    email = men.StringField(max_length=100, required=True)
    path = men.StringField(max_length=100, required=True)
    metadata = men.DictField()
    files = men.DictField()

    # When the document is updated record the
    # location of all files in a new file
    def save(self):
        with open(str(Path(self.path) / 'file_index.tsv'), 'w') as f:
            f.write('{}\t{}\t{}\n'.format(self.owner, self.email, self.access_code))
            f.write('Key\tPath\n')
            for key, file_path in self.files.items():
                # Skip non existent files
                if file_path is None:
                    continue
                # If it's a key for an analysis point to the file index for that analysis
                elif isinstance(file_path, dict):
                    f.write('{}\t{}\n'.format(key, Path(self.path) / key / 'file_index.tsv'))
                # Otherwise just write the value
                else:
                    f.write('{}\t{}\n'.format(key, file_path))
        super(StudyDoc, self).save()

    def __str__(self):
        """ Return a printable string """
        return ppretty(self)

    def generate_AnalysisDoc(self, name, analysis_type, config, access_code=get_salt(20)):
        """ Create a new AnalysisDoc from the current StudyDoc """
        files = {}
        run_id = 0

        # Create a new directory to perform the analysis in
        new_dir = Path(self.path) / '{}_{}'.format(name, run_id).replace('-', '_')
        while new_dir.is_dir():
            run_id += 1
            new_dir = Path(self.path) / '{}_{}'.format(name, run_id).replace('-', '_')

        new_dir = new_dir.resolve()
        new_dir.mkdir()

        # Handle demuxed sequences
        if Path(self.files['for_reads']).suffix in ['.zip', '.tar']:
            (new_dir / 'data.zip').symlink_to(self.files['for_reads'])
            files['data'] = new_dir / 'data.zip'
            data_type = self.reads_type + '_demuxed'
        # Handle all sequences in one file
        else:
            # Create links to the files
            (new_dir / 'barcodes.fastq.gz').symlink_to(self.files['barcodes'])
            (new_dir / 'for_reads.fastq.gz').symlink_to(self.files['for_reads'])

            # Add the links to the files dict for this analysis
            files['barcodes'] = new_dir / 'barcodes.fastq.gz'
            files['for_reads'] = new_dir / 'for_reads.fastq.gz'

            # Handle paired end sequences
            if self.reads_type == 'paired_end':
                # Create links to the files
                (new_dir / 'rev_reads.fastq.gz').symlink_to(self.files['rev_reads'])

                # Add the links to the files dict for this analysis
                files['rev_reads'] = new_dir / 'rev_reads.fastq.gz'
            data_type = self.reads_type

        copy_metadata(self.files['metadata'], new_dir / 'metadata.tsv')
        files['metadata'] = new_dir / 'metadata.tsv'
        string_files = {str(key): str(value) for key, value in files.items()}
        log(config)

        doc = AnalysisDoc(created=datetime.now(),
                          last_accessed=datetime.now(),
                          sub_analysis=False,
                          testing=self.testing,
                          name=new_dir.name,
                          owner=self.owner,
                          email=self.email,
                          path=str(new_dir),
                          study_code=self.access_code,
                          analysis_code=access_code,
                          reads_type=self.reads_type,
                          data_type=data_type,
                          analysis_type=analysis_type,
                          analysis_status='created',
                          config=config,
                          files=string_files)
        doc.save()
        return doc


class AnalysisDoc(men.Document):
    created = men.DateTimeField()
    last_accessed = men.DateTimeField()
    sub_analysis = men.BooleanField(required=True)
    testing = men.BooleanField(required=True)
    name = men.StringField(max_length=100, required=True)
    owner = men.StringField(max_length=100, required=True)
    email = men.StringField(max_length=100, required=True)
    path = men.StringField(max_length=100, required=True)
    study_code = men.StringField(max_length=50, required=True)
    analysis_code = men.StringField(max_length=50, required=True)
    reads_type = men.StringField(max_length=45, required=True)
    data_type = men.StringField(max_length=45, required=True)
    analysis_type = men.StringField(max_length=45, required=True)
    # Stages: created, started, <Name of last method>, finished, errored
    analysis_status = men.StringField(max_length=45, required=True)
    files = men.DictField()
    config = men.DictField()

    def __str__(self):
        """ Return a printable string """
        return ppretty(self)

    def create_sub_analysis(self, category, value):
        """ Creates a new AnalysisDoc for a child analysis """
        print('create sub analysis from {}'.format(self.name))
        child = deepcopy(self)
        child.files = self.files
        child.created = datetime.now()
        child.last_accessed = datetime.now()
        child.sub_analysis = True
        return child

    # When the document is updated record the
    # location of all files in a new file
    def save(self):
        with open(str(Path(self.path) / 'file_index.tsv'), 'w') as f:
            f.write('{}\t{}\t{}\n'.format(self.owner, self.email, self.analysis_code))
            f.write('Key\tPath\n')
            for key, file_path in self.files.items():
                # Skip non existent files
                if file_path is None:
                    continue
                # If it's a key for an analysis point to the file index for that analysis
                elif isinstance(file_path, dict):
                    f.write('{}\t{}\n'.format(key, Path(self.path) / key / 'file_index.tsv'))
                # Otherwise just write the value
                else:
                    f.write('{}\t{}\n'.format(key, file_path))
        super(AnalysisDoc, self).save()


class MMEDSProcess(men.Document):
    status = men.StringField(max_length=100, required=True)
    pid = men.IntField(required=True)  # -1 if it hasn't started yet, -2 if it's finished
    queue_position = men.IntField(required=True)  # -1 if it hasn't started yet, -2 if it's finished
    ptype = men.StringField(max_length=100, required=True)
    associated_doc = men.StringField(max_length=100, required=True)  # Access code for associated document

    def __str__(self):
        """ Return a printable string """
        return ppretty(self)
