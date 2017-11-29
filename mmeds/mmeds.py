from subprocess import run, PIPE
import csv

NAs = ['n/a', 'n.a.', 'n_a', 'na', 'N/A', 'N.A.', 'N_A']


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


def check_header(header, prev_headers):
    """ Check the header field to ensure it complies with MMEDS requirements. """
    errors = []

    # Get the index of the current column (Starting at 1)
    col_index = len(prev_headers)

    # Check if it's a duplicate
    if header in prev_headers:
        errors.append('%s found in header %d times.  ' %
                      (header, prev_headers.count(header) + 1),
                      'Header fields must be unique.\t%d,%d' % (0, col_index))
    # Check if it's numeric
    elif is_numeric(header):
        errors.append('Column names cannot be numbers. Replace column ' +
                      str(col_index) + ' header ' + header)
    # Check if it's NA
    elif header in NAs + ['NA']:
        errors.append('Column names cannot be NA. Replace column ' +
                      str(col_index) + ' header ' + header)
    return errors


def check_column(col, prev_headers):
    """ Validate that there are no issues with the provided column of metadata """

    col = list(col)
    # Get the header
    header = col.pop(0)

    # Check the header
    errors = check_header(header, prev_headers)

    # Get the index of the current column (Starting at 1)
    col_index = len(prev_headers) + 1

    numeric_col = is_numeric(col[0])

    # Check the remaining columns
    for i, cell in enumerate(col):

        # Check for non-standard NAs
        if cell in NAs:
            errors.append("Non standard NA format %s\t%d,%d" %
                          (cell, i, col_index))

        # Check for consistent types in the column
        if is_numeric(cell) and not numeric_col:
                errors.append("Mixed strings and numbers in %s\t%d,%d" %
                              (cell, i, col_index))
    return errors


def validate_mapping_file(file_fp):
    """
    Checks the mapping file at file_fp for any errors.
    Returns a list of the errors, an empty list means there
    were no issues.
    """

    errors = []
    c_reader = csv.reader(file_fp, delimiter='\t')
    columns = list(zip(*c_reader))
    column_headers = []
    for col in columns:
        errors += check_column(col, column_headers)
        column_headers.append(col[0])
    return errors


def is_numeric(s):
    """ Check if the provided string is a number. """
    try:
        float(s)
        return True
    except ValueError:
        pass
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False
