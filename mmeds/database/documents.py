import mongoengine as men
from enum import Enum
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from ppretty import ppretty
from mmeds.config import DOCUMENT_LOG
from mmeds.util import copy_metadata  # , camel_case
# from mmeds.error import AnalysisError
from mmeds.logging import Logger


class DocType(Enum):
    STUDY = 0
    ANALYSIS = 1
    METADATA = 2
    DATA = 3
    FEATURE_TABLE = 4


class MMEDSDoc(men.Document):
    """
    Class for MongoDB documents used in MMEDS
    =========================================
    Note: If this class is modified it's often necessary to clear all
    the existing documents that use the old specification from the database.
    Otherwise MongoEngine will complain about certain document properties not
    existing.
    """
    meta = {'allow_inheritance': True}

    created = men.DateTimeField(require=True)               # Datetime stamp of document creation
    last_accessed = men.DateTimeField(required=True)
    public = men.BooleanField()
    testing = men.BooleanField(required=True)
    owner = men.StringField(max_length=100, required=True)
    email = men.StringField(max_length=100)
    path = men.StringField(max_length=300)
    access_code = men.StringField(max_length=50)
    doc_type = men.EnumField(DocType, required=True)
    is_alive = men.BooleanField()
    exit_code = men.IntField()

    # When the document is updated record the
    # location of all files in a new file
    def save(self, **kwargs):
        Logger.error(f"Saving MongoDB Document of type {self.doc_type}")
        super().save(**kwargs)

    def __str__(self):
        """ Return a printable string """
        return ppretty(self, seq_length=20)

    def get_info(self):
        """ Method for return a dictionary of relevant info for the process log """
        info = {
            'created': self.created,
            'owner': self.owner,
            'access_code': self.access_code,
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

    def generate_MMEDSDoc(self, name, workflow_type, analysis_type, config, access_code, analysis_name="analysis"):
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


class StudyDoc(MMEDSDoc):
    """
    MongoDB Document for storing studies
    """
    study_name = men.StringField()
    path = men.StringField()
    metadata = men.ReferenceField(MMEDSDoc)
    data = men.ListField(men.ReferenceField(MMEDSDoc))
    analyses = men.ListField(men.ReferenceField(MMEDSDoc))


class AnalysisDoc(MMEDSDoc):
    """
    MongoDB Document for storing analyses
    """
    analysis_name = men.StringField()
    path = men.StringField()
    study = men.ReferenceField(MMEDSDoc)
    workflow_type = men.StringField()
    config = men.FileField()


class MetadataDoc(MMEDSDoc):
    """
    MongoDB Document for storing metadata
    """
    study = men.ReferenceField(MMEDSDoc)
    subject_file = men.FileField()
    specimen_file = men.FileField()
    full_metadata_file = men.FileField()
    qiime_file = men.FileField()
    latest_version = men.BooleanField()


class DataDoc(MMEDSDoc):
    """
    MongoDB Document for storing raw data
    """
    data_name = men.StringField()
    data_type = men.StringField()
    studies = men.ListField(men.ReferenceField(MMEDSDoc))
    files = men.MapField(field=men.FileField())
    latest_version = men.BooleanField()


class FeatureTableDoc(MMEDSDoc):
    """
    MongoDB Document for storing feature tables
    """
    table_name = men.StringField()
    studies = men.ListField(men.ReferenceField(MMEDSDoc))
    from_analysis = men.ReferenceField(MMEDSDoc)
    table = men.FileField()
    latest_version = men.BooleanField()
