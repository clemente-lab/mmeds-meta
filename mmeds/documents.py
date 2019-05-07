import mongoengine as men
from datetime import datetime
from pathlib import Path
from mmeds.config import get_salt


class StudyDoc(men.DynamicDocument):
    created = men.DateTimeField()
    last_accessed = men.DateTimeField()
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
        self_string = 'Created: {created}\n last_accessed: {last_accessed}\n study_type: {study_type}\n' +\
            'reads_type: {reads_type}\n study: {study}\n access_code: {access_code}\n owner: {owner}\n' +\
            'email: {email}\n path: {path}\n'
        self_string = self_string.format(created=self.created, last_accessed=self.last_accessed,
                                         study_type=self.study_type, reads_type=self.reads_type,
                                         study=self.study, access_code=self.access_code,
                                         owner=self.owner, email=self.email, path=self.path)
        self_string += 'files: {}\n'.format(self.files.keys())
        return self_string

    def generate_AnalysisDoc(self, path, access_code=get_salt(20)):
        return AnalysisDoc(created=datetime.now(),
                           last_accessed=datetime.now(),
                           owner=self.owner,
                           email=self.email,
                           path=path,
                           study_access_code=self.access_code,
                           access_code=access_code,
                           reads_type=self.reads_type)


class AnalysisDoc(men.DynamicDocument):
    created = men.DateTimeField()
    last_accessed = men.DateTimeField()
    owner = men.StringField(max_length=100, required=True)
    email = men.StringField(max_length=100, required=True)
    path = men.StringField(max_length=100, required=True)
    study_access_code = men.StringField(max_length=50, required=True)
    access_code = men.StringField(max_length=50, required=True)
    reads_type = men.StringField(max_length=45, required=True)
