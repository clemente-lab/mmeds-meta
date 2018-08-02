from pandas import read_csv
from pathlib import Path
from subprocess import run
import os
import multiprocessing as mp

from mmeds.database import Database
from mmeds.config import get_salt, send_email


class Qiime1Analysis:
    """ A class for qiime 1.9.1 analysis of uploaded studies. """

    def __init__(self, owner, access_code):
        self.db = Database('', user='root', owner=owner, connect=False)
        self.access_code = access_code
        self.headers = [
            '#SampleID',
            'BarcodeSequence',
            'LinkerPrimerSequence',
            'Description'
        ]

        files, path = self.db.get_mongo_files(self.access_code)
        self.path = Path(path)

    def __del__(self):
        del self.db

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'source activate qiime1; validate_mapping_file.py -m {}'
        run(cmd.format(files['mapping']), shell=True, check=True)

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

        # Add the split directory to the MetaData object
        self.db.update_metadata(self.access_code, 'split_dir', new_dir)

        # Run the script
        cmd = 'source activate qiime1; split_libraries_fastq.py -o {} -i {} -b {} -m {}'
        command = cmd.format(new_dir, files['reads'], files['barcodes'], files['mapping'])
        run(command, shell=True, check=True)

    def pick_otu(self, reference='closed'):
        """ Run the pick OTU scripts. """
        files, path = self.db.get_mongo_files(self.access_code)
        new_dir = Path(path) / ('otu_output_' + get_salt(10))
        while os.path.exists(new_dir):
            new_dir = Path(path) / ('otu_output_' + get_salt(10))

        # Add the otu directory to the MetaData object
        self.db.update_metadata(self.access_code, 'otu_dir', new_dir)

        with open(Path(path) / 'params.txt', 'w') as f:
            f.write('pick_otus:enable_rev_strand_match True\n')

        # Run the script
        cmd = 'source activate qiime1; pick_{}_reference_otus.py -o {} -i {} -p {}'
        command = cmd.format(reference,
                             new_dir,
                             Path(files['split_dir']) / 'seqs.fna',
                             Path(path) / 'params.txt')
        run(command, shell=True, check=True)

    def core_diversity(self):
        """ Run the core diversity analysis script. """
        files, path = self.db.get_mongo_files(self.access_code)
        new_dir = Path(path) / ('diversity_output_' + get_salt(10))
        while os.path.exists(new_dir):
            new_dir = Path(path) / ('diversity_output_' + get_salt(10))

        # Add the otu directory to the MetaData object
        self.db.update_metadata(self.access_code, 'diversity_dir', new_dir)

        # Run the script
        cmd = 'source activate qiime1; core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {}'
        command = cmd.format(new_dir,
                             Path(files['otu_dir']) / 'otu_table_mc2_w_tax_no_pynast_failures.biom',
                             files['mapping'],
                             Path(files['otu_dir']) / 'rep_set.tre',
                             1114)
        run(command, shell=True, check=True)

    def analysis(self):
        """ Perform some analysis. """
        self.create_qiime_mapping_file()
        self.validate_mapping()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
        doc = self.db.get_metadata(self.access_code)
        send_email(doc.email, doc.owner, 'analysis', study_name=doc.study)


class Qiime2Analysis:
    """ A class for qiime 2 analysis of uploaded studies. """

    def __init__(self, owner, access_code):
        self.db = Database('', user='root', owner=owner, connect=False)
        self.access_code = access_code
        self.headers = [
            '#SampleID',
            'BarcodeSequence',
            'LinkerPrimerSequence',
            'Description'
        ]

        files, path = self.db.get_mongo_files(self.access_code)
        self.path = Path(path)

    def __del__(self):
        del self.db

    def setup_dir(self):
        """ Setup the directory to run the analysis. """
        files, path = self.db.get_mongo_files(self.access_code)

        new_dir = Path(path) / ('working_dir' + get_salt(10))
        while os.path.exists(new_dir):
            new_dir = Path(path) / ('working_dir' + get_salt(10))
        # Create links to the files
        run('ln {} {}'.format(files['barcodes'], new_dir / 'barcodes.fastq.gz'))
        run('ln {} {}'.format(files['reads'], new_dir / 'sequences.fastq.gz'))

        # Add the split directory to the MetaData object
        self.db.update_metadata(self.access_code, 'working_dir', new_dir)

    def validate_mapping(self):
        """ Run validation on the Qiime mapping file """
        files, path = self.db.get_mongo_files(self.access_code)
        cmd = 'source activate qiime2; validate_mapping_file.py -m {}'
        run(cmd.format(files['mapping']), shell=True, check=True)

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

        # Add the split directory to the MetaData object
        self.db.update_metadata(self.access_code, 'split_dir', new_dir)

        # Run the script
        cmd = 'source activate qiime2; split_libraries_fastq.py -o {} -i {} -b {} -m {}'
        command = cmd.format(new_dir, files['reads'], files['barcodes'], files['mapping'])
        run(command, shell=True, check=True)

    def pick_otu(self, reference='closed'):
        """ Run the pick OTU scripts. """
        files, path = self.db.get_mongo_files(self.access_code)
        new_dir = Path(path) / ('otu_output_' + get_salt(10))
        while os.path.exists(new_dir):
            new_dir = Path(path) / ('otu_output_' + get_salt(10))

        # Add the otu directory to the MetaData object
        self.db.update_metadata(self.access_code, 'otu_dir', new_dir)

        with open(Path(path) / 'params.txt', 'w') as f:
            f.write('pick_otus:enable_rev_strand_match True\n')

        # Run the script
        cmd = 'source activate qiime2; pick_{}_reference_otus.py -o {} -i {} -p {}'
        command = cmd.format(reference,
                             new_dir,
                             Path(files['split_dir']) / 'seqs.fna',
                             Path(path) / 'params.txt')
        run(command, shell=True, check=True)

    def core_diversity(self):
        """ Run the core diversity analysis script. """
        files, path = self.db.get_mongo_files(self.access_code)
        new_dir = Path(path) / ('diversity_output_' + get_salt(10))
        while os.path.exists(new_dir):
            new_dir = Path(path) / ('diversity_output_' + get_salt(10))

        # Add the otu directory to the MetaData object
        self.db.update_metadata(self.access_code, 'diversity_dir', new_dir)

        # Run the script
        cmd = 'source activate qiime2; core_diversity_analyses.py -o {} -i {} -m {} -t {} -e {}'
        command = cmd.format(new_dir,
                             Path(files['otu_dir']) / 'otu_table_mc2_w_tax_no_pynast_failures.biom',
                             files['mapping'],
                             Path(files['otu_dir']) / 'rep_set.tre',
                             1114)
        run(command, shell=True, check=True)

    def analysis(self):
        """ Perform some analysis. """
        self.create_qiime_mapping_file()
        self.setup_dir()
        self.validate_mapping()
        self.split_libraries()
        self.pick_otu()
        self.core_diversity()
        doc = self.db.get_metadata(self.access_code)
        send_email(doc.email, doc.owner, 'analysis', study_name=doc.study)


def run_qiime1(user, access_code, version):
    """ Run qiime analysis. """
    qa = Qiime1Analysis(user, access_code)
    qa.analysis()


def run_qiime2(user, access_code, version):
    """ Run qiime analysis. """
    qa = Qiime2Analysis(user, access_code)
    qa.analysis()


def analysis_runner(atype, user, access_code):
    """ Start running the analysis in a new process """
    if atype == 'qiime1':
        p = mp.Process(target=run_qiime1, args=(user, access_code))
    elif atype == 'qiime2':
        p = mp.Process(target=run_qiime2, args=(user, access_code))
    p.start()

    return p
