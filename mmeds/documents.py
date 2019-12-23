import mongoengine as men
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from mmeds.config import DOCUMENT_LOG, TOOL_FILES
from mmeds.util import copy_metadata, log, camel_case, error_log, debug_log
from ppretty import ppretty


class MMEDSDoc(men.Document):
    """ Class for MongoDB documents used in MMEDS """
    created = men.DateTimeField(require=True)               # Datetime stamp of document creation
    last_accessed = men.DateTimeField(required=True)
    public = men.BooleanField()
    testing = men.BooleanField(required=True)
    sub_analysis = men.BooleanField()                       # If this document corresponds to a sub analysis
    name = men.StringField(max_length=100)
    owner = men.StringField(max_length=100, required=True)
    email = men.StringField(max_length=100, required=True)
    path = men.StringField(max_length=256, required=True)
    study_code = men.StringField(max_length=100)
    study_name = men.StringField(max_length=100)
    access_code = men.StringField(max_length=50)
    reads_type = men.StringField(max_length=45)
    barcodes_type = men.StringField(max_length=45)
    data_type = men.StringField(max_length=45)
    doc_type = men.StringField(max_length=45)

    # Stages: created, started, <Name of last method>, finished, errored
    analysis_status = men.StringField(max_length=45)
    restart_stage = men.IntField()
    pid = men.IntField()
    files = men.DictField()
    config = men.DictField()

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
        with open(DOCUMENT_LOG, 'a') as f:
            f.write('-\t'.join([str(type(self)), self.owner, 'Upload', 'Finished', self.path, self.access_code]) + '\n')
        super().save()

    def __str__(self):
        """ Return a printable string """
        return ppretty(self, seq_length=20)

    def generate_analysis_doc(self, atype, access_code):
        """
        Creates a new AnalysisDoc for a child analysis
        ==============================================
        :atype: A string. The type of analysis this doc corresponds to
        :access_code: A string. The code for accessing this analysis
        """
        debug_log('create analysis atype: {}, code: {}'.format(atype, access_code))

        child_path = Path(self.path) / camel_case(atype)
        child_path.mkdir()

        child_files = deepcopy(self.files)
        child_files['metadata'] = str(child_path / 'metadata.tsv')

        child_config = deepcopy(self.config)
        child_config['sub_analysis'] = 'None'

        child = MMEDSDoc(created=datetime.now(),
                         last_accessed=datetime.now(),
                         sub_analysis=True,
                         testing=self.testing,
                         name=child_path.name,
                         owner=self.owner,
                         email=self.email,
                         path=str(child_path),
                         study_code=self.study_code,
                         study_name=self.study_name,
                         access_code=access_code,
                         reads_type=self.reads_type,
                         data_type=self.data_type,
                         doc_type=self.doc_type,
                         analysis_status='Pending',
                         restart_stage='0',
                         files=child_files,
                         config=child_config)

        # Update the child's attributes
        child.save()
        debug_log(child)
        return child

    def generate_sub_analysis_doc(self, category, value, analysis_code):
        """ Creates a new AnalysisDoc for a child analysis """
        log('create sub analysis cat: {}, val: {}, code: {}'.format(category, value, analysis_code))

        child_path = Path(self.path) / camel_case('{}_{}'.format(category[1], value))
        child_path.mkdir()

        child_files = deepcopy(self.files)
        child_files['metadata'] = str(child_path / 'metadata.tsv')

        child_config = deepcopy(self.config)
        child_config['sub_analysis'] = 'None'
        child_config['metadata'] = [cat for cat in self.config['metadata'] if not cat == category[1]]

        child = MMEDSDoc(created=datetime.now(),
                         last_accessed=datetime.now(),
                         sub_analysis=True,
                         testing=self.testing,
                         name=child_path.name,
                         owner=self.owner,
                         email=self.email,
                         path=str(child_path),
                         study_code=self.study_code,
                         study_name=self.study_name,
                         access_code=analysis_code,
                         reads_type=self.reads_type,
                         barcodes_type=self.barcodes_type,
                         data_type=self.data_type,
                         doc_type=self.doc_type,
                         analysis_status='Pending',
                         restart_stage='0',
                         files=child_files,
                         config=child_config)

        # Update the child's attributes
        child.save()
        debug_log(child)
        debug_log('Created with {}, {}, {}, {}'.format(category, value, analysis_code, child_path))
        return child

    def generate_MMEDSDoc(self, name, atype, config, access_code):
        """
        Create a new AnalysisDoc from the current StudyDoc.
        :name: A string. The name of the new document.
        :doc_type: A string. The type of analysis the new document will store information on.
        :config: A dictionary. The configuration for the analysis.
        :access_code: A string. A unique code for accessing the new document.
        :files: A list of strings. Keys for the files to link to from the parents doc
        """
        tool_type, data_type = atype.split('-')
        # Create a new directory to perform the analysis in
        run_id = 0
        new_dir = Path(self.path) / '{}_{}'.format(self.name, run_id)
        while new_dir.is_dir():
            run_id += 1
            new_dir = Path(self.path) / '{}_{}'.format(self.name, run_id)

        new_dir = new_dir.resolve()
        new_dir.mkdir()

        files = {}
        for file_key in TOOL_FILES[tool_type]:
            # Create links to the files if they exist
            if self.files.get(file_key) is not None:
                (new_dir / Path(self.files[file_key]).name).symlink_to(self.files[file_key])
                files[file_key] = new_dir / Path(self.files[file_key]).name
        """
        if 'qiime' in doc_type:
            # Handle demuxed sequences
            if Path(self.files['for_reads']).suffix in ['.zip', '.tar']:
                (new_dir / 'data.zip').symlink_to(self.files['for_reads'])
                files['data'] = new_dir / 'data.zip'
                data_type = self.reads_type + '_demuxed'
            # Handle all sequences in one file
            else:
                if 'single' in self.barcodes_type:
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
                elif 'dual' in self.barcodes_type:
                    # Create links to the files
                    (new_dir / 'for_barcodes.fastq.gz').symlink_to(self.files['for_barcodes'])
                    (new_dir / 'for_reads.fastq.gz').symlink_to(self.files['for_reads'])
                    (new_dir / 'rev_barcodes.fastq.gz').symlink_to(self.files['rev_barcodes'])
                    (new_dir / 'rev_reads.fastq.gz').symlink_to(self.files['rev_reads'])

                    # Add the links to the files dict for this analysis
                    files['for_barcodes'] = new_dir / 'for_barcodes.fastq.gz'
                    files['for_reads'] = new_dir / 'for_reads.fastq.gz'
                    files['rev_barcodes'] = new_dir / 'rev_barcodes.fastq.gz'
                    files['rev_reads'] = new_dir / 'rev_reads.fastq.gz'

                data_type = self.reads_type
        elif 'sparcc' in doc_type:
            data_type = 'otu_table'
            (new_dir / 'otu_table.tsv').symlink_to(self.files['otu_table'])
            files['otu_table'] = new_dir / 'otu_table.tsv'
        elif 'test' in doc_type:
            data_type = 'test_data'
        else:
            raise AnalysisError('Invalid type for analysis {}'.format(doc_type))
        """

        copy_metadata(self.files['metadata'], new_dir / 'metadata.tsv')
        files['metadata'] = new_dir / 'metadata.tsv'
        string_files = {str(key): str(value) for key, value in files.items()}

        log('creating analysis doc')
        doc = MMEDSDoc(created=datetime.now(),
                       last_accessed=datetime.now(),
                       sub_analysis=False,
                       testing=self.testing,
                       name=new_dir.name,
                       owner=self.owner,
                       email=self.email,
                       path=str(new_dir),
                       study_code=self.access_code,
                       study_name=self.study_name,
                       access_code=access_code,
                       reads_type=self.reads_type,
                       barcodes_type=self.barcodes_type,
                       doc_type='{}-{}'.format(tool_type, data_type),
                       data_type=data_type,
                       analysis_status='created',
                       restart_stage=0,
                       config=config,
                       files=string_files)

        error_log(ppretty(doc))
        doc.save()
        with open(DOCUMENT_LOG, 'a') as f:
            f.write('-\t'.join([str(x) for x in [doc.study_name, doc.owner, doc.doc_type, doc.analysis_status,
                                                 datetime.now(), doc.path, doc.access_code]]) + '\n')
            log('saved analysis doc')
        return doc
