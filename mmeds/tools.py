from pandas import read_csv
from pathlib import Path
from subprocess import run
import os

from mmeds.database import Database
from mmeds.config import get_salt


class QiimeAnalysis:
    """ A class for analysis qiime analysis of uploaded studies. """

    def __init__(self, path, owner, access_code):
        self.path = path
        self.db = Database(path, user='root', owner=owner)
        self.access_code = access_code
        self.headers = [
            '#SampleID',
            'BarcodeSequence',
            'LinkerPrimerSequence',
            'Description'
        ]

    def __del__(self):
        del self.db

    def run_qiime(self, read1, read2, mapping_file, path):
        """
        Function for loading the qiime package and running it on
        the specified files.
        """
        filename = 'newfile.txt'
        run('source activate qiime1; python --version; echo "{}\n{}\n{}\n"&>{}'.format(read1, read2, mapping_file, path / filename), shell=True)
        return filename

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        run('source activate qiime1; validate_mapping_file.py -m {}'.format(files['mapping']), shell=True)

    def create_qiime_mapping_file(self):
        """ Create a qiime mapping file from the metadata """
        # Open the metadata file for the study
        metadata = self.db.get_metadata(self.access_code)
        fp = metadata.files['metadata']
        with open(fp) as f:
            mdata = read_csv(f, header=[0, 1], sep='\t')

        # Create the Qiime mapping file
        mapping_file = self.path / 'qiime_mapping_file.tsv'
        with open(mapping_file, 'w') as f:
            f.write('\t'.join(self.headers) + '\n')
            for row_index in range(len(mdata)):
                row = []
                for header in self.headers:
                    if header == '#SampleID':
                        row.append(mdata['Specimen']['SampleID'][row_index])
                    else:
                        row.append(mdata['Specimen'][header][row_index])
                f.write('\t'.join(row) + '\n')

        # Add the mapping file to the MetaData object
        self.db.update_metadata(self.access_code, 'mapping', mapping_file)

    def split_libraries(self):
        """ Split the libraries and perform quality analysis. """
        files, path = self.db.get_mongo_files(self.access_code)
        new_dir = Path(path) / ('split_output_' + get_salt(10))
        while os.path.exists(new_dir):
            new_dir = Path(path) / ('split_output_' + get_salt(10))
        os.makedirs(new_dir)

        # Add the split directory to the MetaData object
        self.db.update_metadata(self.access_code, 'split_dir', new_dir)

        cmd = 'source activate qiime1; split_libraries_fastq.py -o {} -i {} -b {} -m {}'
        command = cmd.format(new_dir, files['reads'], files['barcodes'], files['mapping'])
        completed_process = run(command, shell=True, check=True)
        return completed_process.stdout

    def pick_otu(self, reference='open'):
        """ Run the pick OTU scripts. """
        files, path = self.db.get_mongo_files(self.access_code)
        new_dir = Path(path) / ('otu_output_' + get_salt(10))
        while os.path.exists(new_dir):
            new_dir = Path(path) / ('otu_output_' + get_salt(10))

        with open(Path(path) / 'params.txt', 'w') as f:
            f.write('pick_otus:enable_rev_strand_match True\n')

        cmd = 'source activate qiime1; pick_open_reference_otus.py -o {} -i {} -p {}'
        command = cmd.format(new_dir, Path(files['split_dir']) / 'seqs.fna', Path(path) / 'params.txt')
        completed_process = run(command, shell=True, check=True)
        return completed_process.stdout

    def analysis(self):
        """ Perform some analysis. """
        self.create_qiime_mapping_file()
        self.validate_mapping()
        self.split_libraries()
        result = self.pick_otu()
        return result
