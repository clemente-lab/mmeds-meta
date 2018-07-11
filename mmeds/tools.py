from subprocess import run
from os.path import join


def run_qiime(read1, read2, mapping_file, path):
    """
    Function for loading the qiime package and running it on
    the specified files.
    """
    filename = 'newfile.txt'
    run('source activate qiime1; python --version; echo "{}\n{}\n{}\n"&>{}'.format(read1, read2, mapping_file, join(path, filename)), shell=True)

    return filename
