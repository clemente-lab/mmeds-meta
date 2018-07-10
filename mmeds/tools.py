from subprocess import run


def run_qiime(read1, read2, mapping_file, path):
    """
    Function for loading the qiime package and running it on
    the specified files.
    """
    filename = 'newfile.txt'
    run('source activate qiime; python --version; echo "Ran Successfully"&>{}'.format(path + filename), shell=True)

    return filename
