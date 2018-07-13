from pandas import read_csv

from subprocess import run
from os.path import join
from mmeds.database import Database


class QiimeAnalysis:
    """ A class for analysis qiime analysis of uploaded studies. """

    def __init__(self, path, owner, access_code):
        self.db = Database(path, user='root', owner=owner)
        self.access_code = access_code
        self.qiime_headers = [
            '#SampleID',
            'BarcodeSequence',
            'BarcodeWell'
            'Description'
        ]

    def __del__(self):
        del self.db

    def run_qiime(read1, read2, mapping_file, path):
        """
        Function for loading the qiime package and running it on
        the specified files.
        """
        filename = 'newfile.txt'
        run('source activate qiime1; python --version; echo "{}\n{}\n{}\n"&>{}'.format(read1, read2, mapping_file, join(path, filename)), shell=True)
        return filename

    def create_qiime_mapping_file(self):
        """
        Create a qiime mapping file from the metadata
        """
        metadata = self.db.get_meta_data(self.access_code)
        fp = metadata.files['metadata']

        with open(fp) as f:
            mdata = read_csv(f, header=[0, 1])


