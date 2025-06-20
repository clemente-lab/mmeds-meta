import mongoengine as men
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from ppretty import ppretty
from mmeds.config import DOCUMENT_LOG
from mmeds.util import copy_metadata, camel_case
from mmeds.error import AnalysisError
from mmeds.logging import Logger


class MMEDSDoc(men.Document):
    """
    Class for MongoDB documents used in MMEDS
    =========================================
    Note: If this class is modified it's often necessary to clear all
    the existing documents that use the old specification from the database.
    Otherwise MongoEngine will complain about certain document properties not
    existing.
    """
    created = men.DateTimeField(require=True)               # Datetime stamp of document creation
    last_accessed = men.DateTimeField(required=True)
    public = men.BooleanField()
    testing = men.BooleanField(required=True)
    sub_analysis = men.BooleanField()                       # If this document corresponds to a sub analysis
    is_alive = men.BooleanField()  # If the process it's related to is currently running
    name = men.StringField(max_length=100)
    owner = men.StringField(max_length=100, required=True)
    email = men.StringField(max_length=100)
    path = men.StringField(max_length=256)
    study_code = men.StringField(max_length=100)
    study_name = men.StringField(max_length=100)
    access_code = men.StringField(max_length=50)
    reads_type = men.StringField(max_length=45)     # single_end or paired_end
    barcodes_type = men.StringField(max_length=45)  # Single or Paired
    data_type = men.StringField(max_length=45)  #
    workflow_type = men.StringField(max_length=45)  # Type of tool
    doc_type = men.StringField(max_length=45)  # Study, Analysis, or SequencingRun
    analysis_type = men.StringField(max_length=45)
    analysis_name = men.StringField(max_length=45)

    # Stages: created, started, <Name of last method>, finished, errored
    analysis_status = men.StringField(max_length=45)
    restart_stage = men.IntField()
    pid = men.IntField()
    exit_code = men.IntField()
    files = men.DictField()
    config = men.DictField()

    # When the document is updated record the
    # location of all files in a new file
    def save(self, **kwargs):
        super().save(**kwargs)
        if self.path is not None:
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
                f.write('-\t'.join([str(type(self)), self.owner, 'Upload', 'Finished',
                                    self.path, self.access_code]) + '\n')

    def __str__(self):
        """ Return a printable string """
        return ppretty(self, seq_length=20)

    def get_info(self):
        """ Method for return a dictionary of relevant info for the process log """
        info = {
            'created': self.created,
            'owner': self.owner,
            'stage': self.restart_stage,
            'study_code': self.study_code,
            'access_code': self.access_code,
            'type': self.analysis_type,
            'pid': self.pid,
            'path': self.path,
            'name': self.name,
            'is_alive': self.is_alive
        }
        writeable = {}
        for key, item in info.items():
            if item is None:
                writeable[key] = None
            elif isinstance(item, bool):
                writeable[key] = bool(deepcopy(item))
            else:
                writeable[key] = str(deepcopy(item))
        return writeable

    def generate_MMEDSDoc(self, name, workflow_type, analysis_type, config, access_code, analysis_name = "analysis"):
        """
        Create a new AnalysisDoc from the current StudyDoc.
        :name: A string. The name of the new document.
        :doc_type: A string. The type of analysis the new document will store information on.
        :config: A dictionary. The configuration for the analysis.
        :access_code: A string. A unique code for accessing the new document.
        :files: A list of strings. Keys for the files to link to from the parents doc
        """
        # Create a new directory to perform the analysis in
        run_id = 0
        new_dir = Path(self.path) / '{}_{}_{}'.format(name, analysis_name, run_id)
        while new_dir.is_dir():
            run_id += 1
            new_dir = Path(self.path) / '{}_{}_{}'.format(name, analysis_name, run_id)
        new_dir = new_dir.resolve()
        new_dir.mkdir()

        files = {}
        Logger.debug('Creating analysis {}'.format(name))
        copy_metadata(self.files['metadata'], new_dir / 'metadata.tsv')
        files['metadata'] = new_dir / 'metadata.tsv'
        string_files = {str(key): str(value) for key, value in files.items()}

        doc = MMEDSDoc(created=datetime.now(),
                       last_accessed=datetime.now(),
                       sub_analysis=False,
                       testing=self.testing,
                       is_alive=True,
                       name=new_dir.name,
                       owner=self.owner,
                       email=self.email,
                       path=str(new_dir),
                       study_code=str(self.access_code),
                       study_name=self.study_name,
                       access_code=str(access_code),
                       reads_type=self.reads_type,
                       barcodes_type=self.barcodes_type,
                       doc_type='analysis',
                       workflow_type=workflow_type,
                       data_type=self.data_type,
                       analysis_type=analysis_type,
                       analysis_name=analysis_name,
                       analysis_status='created',
                       restart_stage=0,
                       config=config,
                       files=string_files)

        doc.save(check=True)
        with open(DOCUMENT_LOG, 'a') as f:
            f.write('-\t'.join([str(x) for x in [doc.study_name, doc.owner, doc.doc_type, doc.analysis_status,
                                                 datetime.now(), doc.path, doc.access_code]]) + '\n')
            Logger.debug('saved analysis doc')
        return doc
