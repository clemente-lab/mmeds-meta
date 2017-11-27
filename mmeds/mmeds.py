from subprocess import run, PIPE


def check_metadata(file_fp, directory):
    """
    Execute QIIME to check the metadata file provided.
    """
    sac = 'source activate qiime1; '
    cd = 'cd ' + directory + '; '
    call_string = sac + cd + 'validate_mapping_file.py -m ' + file_fp
    result = run(call_string, stdout=PIPE, shell=True, check=True)
    # Return the result of the call
    return result.stdout
