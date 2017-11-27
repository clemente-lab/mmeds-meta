from subprocess import run, PIPE


def check_metadata(file_fp, directory):
    """
    Execute QIIME to check the metadata file provided.
    """
    sac = 'source activate qiime; '
    cd = 'cd ' + directory + '; '
    call_string = sac + cd + 'validate_mapping_file.py -m ' + file_fp
    result = run(call_string, stdout=PIPE, shell=True, check=True)
    # Return the result of the call
    return result.stdout


def insert_error(page, line_number, error_message):
    """ Inserts an error message in the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] + ['<font color="red">' + error_message + '</font>'] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page
