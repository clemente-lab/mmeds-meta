from subprocess import run


def check_metadata(file_fp):
    """
    Execute QIIME to check the metadata file provided.
    """
    sac = 'source activate qiime'
    call_string = sac + 'validate_mapping_file.py ' + file_fp
    try:
        run(call_string, shell=True, check=True)
        return 0
    except ValueError:
        return 1
