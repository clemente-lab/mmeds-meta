from subprocess import run, PIPE
from collections import defaultdict
import csv
import cherrypy

NAs = ['n/a', 'n.a.', 'n_a', 'na', 'N/A', 'N.A.', 'N_A']

REQUIRED_HEADERS = set(['Description', '#SampleID', 'BarcodeSequence', 'LinkerPrimerSequence', 'Lab', 'AnalysisTool', 'PrimaryInvestigator'])

HIPAA_HEADERS = ['name', 'social_security', 'social_security_number', 'address', 'phone', 'phone_number']

DNA = set('GATC')

ILLEGAL_IN_HEADER = set('/\\ ')
ILLEGAL_IN_CELL = set(str(ILLEGAL_IN_HEADER) + '_')


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

    row_col = '0\t' + str(col_index) + '\t'

    # Check if it's a duplicate
    if header in prev_headers:
        errors.append(row_col + '%s found in header %d times.  ' %
                      (header, prev_headers.count(header) + 1) +
                      'Header fields must be unique. Replace header %s of column\t%d' %
                      (header, col_index))
    # Check if it's numeric
    elif is_numeric(header):
        errors.append(row_col + 'Column names cannot be numbers. Replace header %s of column\t%d ' %
                      (header, col_index))
    # Check if it's NA
    elif header in NAs + ['NA']:
        errors.append(row_col + 'Column names cannot be NA. Replace  header %s of column\t%d ' %
                      (header, col_index))
    # Check for illegal characters
    elif ILLEGAL_IN_HEADER.intersection(set(header)):
        illegal_chars = ILLEGAL_IN_HEADER.intersection(set(header))
        errors.append(row_col + 'Illegal character(s) %s. Replace header %s of column\t%d' %
                      (' '.join(illegal_chars), header, col_index))
    # Check for HIPAA non-compliant headers
    elif header.lower() in HIPAA_HEADERS:
        errors.append(row_col + 'Potentially identifying information in %s of column\t%d' %
                      (header, col_index))
    return errors


def check_column(column, prev_headers):
    """ Validate that there are no issues with the provided column of metadata """

    # Get the header
    header = column[0]
    # Get the rest of the column
    col = column[1:]

    # Check the header
    errors = check_header(header, prev_headers)

    # Get the index of the current column (Starting at 1)
    col_index = len(prev_headers) + 1

    numeric_col = is_numeric(col[0])

    # Check the remaining columns
    for i, cell in enumerate(col):
        row_col = str(i) + '\t' + str(col_index) + '\t'
        # Check for non-standard NAs
        if cell in NAs:
            errors.append(row_col + 'Non standard NA format %s\t%d,%d' %
                          (cell, i, col_index))

        # Check for consistent types in the column
        elif is_numeric(cell) and not numeric_col:
                errors.append(row_col + 'Mixed strings and numbers in %s\t%d,%d' %
                              (cell, i, col_index))
        # Check for empty fields
        elif '' == cell:
            errors.append(row_col + 'Empty cell value %s' % cell)
    return errors


def check_duplicates(column, col_index):
    """ Checks for any duplicate entries in the provided column """

    errors = []
    cells = defaultdict(list)

    # Add the indices of each item
    for i, cell in enumerate(column):
        cells[cell].append(i)
    # Find any duplicates
    dups = {k: v for k, v in cells.items() if len(v) > 1}
    for dup_key in dups.keys():
        value = dups[dup_key]
        for val in value[1:]:
            errors.append('%d\t%d\tValue %s in row %d duplicate of row %d.' %
                          (val, col_index, dup_key, val, value[0]))
    return errors


def check_lengths(column, col_index):
    """ Checks that all entries have the same length in the provided column """
    errors = []
    length = len(column[1])
    for i, cell in enumerate(column[2:]):
        if not len(cell) == length:
            errors.append('%d\t%d\tValue %s has a different length from other values in column %d' %
                          (i + 2, col_index, cell, col_index))
    return errors


def check_barcode_chars(column, col_index):
    """ Check that BarcodeSequence only contains valid DNA characters. """
    errors = []
    for i, cell in enumerate(column[1:]):
        diff = set(cell).difference(DNA)
        if diff:
            errors.append('%d\t%d\tInvalid BarcodeSequence char(s) %s in row %d' %
                          (i + 1, col_index, ', '.join(diff), i + 1))
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
    for i, col in enumerate(columns):
        errors += check_column(col, column_headers)
        column_headers.append(col[0])

        # Perform column specific checks
        if col[0] == 'Description' and col[0] != columns[-1][0]:
            errors.append('Description is not the last column in the metadata file\t%d,%d' %
                          (0, columns.index(col)))
        elif col[0] == 'BarcodeSequence':
            errors += check_duplicates(col, i)
            errors += check_lengths(col, i)
            errors += check_barcode_chars(col, i)
        elif col[0] == '#SampleID':
            errors += check_duplicates(col, i)
        elif col[0] == 'LinkerPrimerSequence':
            errors += check_lengths(col, i)

    cherrypy.log('\n'.join(column_headers))
    missing_headers = REQUIRED_HEADERS.difference(column_headers)

    if missing_headers:
        errors.append('Missing requires fields: ' + ', '.join(missing_headers))

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
