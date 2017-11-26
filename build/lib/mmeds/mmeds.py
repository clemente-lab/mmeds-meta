from subprocess import run, PIPE


def check_metadata(file_fp):
    """
    Execute QIIME to check the metadata file provided.
    """
    sac = 'source activate qiime; '
    call_string = sac + 'validate_mapping_file.py -m ' + file_fp
    result = run(call_string, stdout=PIPE, shell=True, check=True)
    # Return the result of the call
    return result.stdout
