from collections import defaultdict
from numpy import std, mean, issubdtype, number
from mmeds.config import STORAGE_DIR
from os.path import join
import pandas as pd

NAs = ['n/a', 'n.a.', 'n_a', 'na', 'N/A', 'N.A.', 'N_A']

REQUIRED_HEADERS = set(['Description', '#SampleID', 'BarcodeSequence', 'LinkerPrimerSequence', 'Lab', 'AnalysisTool', 'PrimaryInvestigator'])

REQUIRED_HEADERS = set(['SampleID', 'BarcodeSequence', 'PrimaryInvestigator'])

HIPAA_HEADERS = ['name', 'social_security', 'social_security_number', 'address', 'phone', 'phone_number']

DNA = set('GATC')

ILLEGAL_IN_HEADER = set('/\\ *?')  # Limit to alpha numeric, underscore, dot, hyphen, has to start with alpha
ILLEGAL_IN_CELL = set(str(ILLEGAL_IN_HEADER) + '_')


def insert_error(page, line_number, error_message):
    """ Inserts an error message in the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] + ['<p><font color="red">' + error_message + '</font></p>'] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def insert_warning(page, line_number, error_message):
    """ Inserts an error message in the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] + ['<p><font color="orange">' + error_message + '</font></p>'] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def insert_html(page, line_number, html):
    """ Inserts additional HTML into the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] + ['<p>' + html + '</p>'] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def check_header(header, col_index):
    """ Check the header field to ensure it complies with MMEDS requirements. """
    errors = []

    row_col = '0\t' + str(col_index) + '\t'

    # Check if it's numeric
    if is_numeric(header):
        errors.append(row_col + 'Column names cannot be numbers. Replace header %s of column\t%d ' %
                      (header, col_index))
    # Check if it's NA
    if header in NAs + ['NA']:
        errors.append(row_col + 'Column names cannot be NA. Replace  header %s of column\t%d ' %
                      (header, col_index))
    # Check for illegal characters
    if ILLEGAL_IN_HEADER.intersection(set(header)):
        illegal_chars = ILLEGAL_IN_HEADER.intersection(set(header))
        errors.append(row_col + 'Illegal character(s) %s. Replace header %s of column\t%d' %
                      (' '.join(illegal_chars), header, col_index))
    # Check for HIPAA non-compliant headers
    if header.lower() in HIPAA_HEADERS:
        errors.append(row_col + 'Potentially identifying information in %s of column\t%d' %
                      (header, col_index))
    # Check for trailing or preceding whitespace
    if not header == header.strip():
        errors.append(row_col + 'Preceding or trailing whitespace %s in column %d' %
                      (header, col_index))
    return errors


def check_column(raw_column, col_index):
    """ Validate that there are no issues with the provided column of metadata """
    column = raw_column.astype(type(raw_column[0]))
    # Get the header
    header = column.name

    # Check the header
    errors = check_header(header, col_index)
    warnings = []

    # Ensure there is only one study being uploaded
    if header == 'StudyName' and len(set(column.tolist())) > 1:
        errors.append('-1\t-1\tError: Multiple studies in one metadata file')

    if issubdtype(column.dtype, number):
        stddev = std(column)
        avg = mean(column)

    # Check the remaining columns
    for i, cell in enumerate(column):
        row_col = str(i) + '\t' + str(col_index) + '\t'
        # Check for non-standard NAs
        if cell in NAs:
            errors.append(row_col + 'Non standard NA format %s\t%d,%d' %
                          (cell, i, col_index))

        # Check for consistent types in the column
        # Pandas stores 'str' as 'object' so check for that explicitly
        if not column.dtype == type(cell) and\
           (not isinstance(cell, str) and 'object' == column.dtype):
            errors.append(row_col + 'Mixed datatypes in %s\t%d,%d' %
                          (cell, i, col_index))
        if type(cell) == str:
            # Check for empty fields
            if '' == cell:
                errors.append(row_col + 'Empty cell value %s' % cell)
            # Check for trailing or preceding whitespace
            if not cell == cell.strip():
                errors.append('%d\t%d\tPreceding or trailing whitespace %s in row %d' %
                              (i + 1, col_index, cell, i + 1))
    if issubdtype(column.dtype, number):
        for i, cell in enumerate(column):
            if (cell > avg + (2 * stddev) or cell < avg - (2 * stddev)):
                warnings.append('%d\t%d\tValue %s outside of two standard deviations of mean in column %d' %
                                (i + 1, col_index, cell, i + 1))
    return errors, warnings


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


def check_duplicate_cols(headers):
    """ Returns true if there are any duplicate headers. """
    dups = []
    for header in headers:
        if '.1' in header:
            dups.append(header.split('.')[0])
    return dups


def validate_mapping_file(file_fp, delimiter='\t'):
    """
    Checks the mapping file at file_fp for any errors.
    Returns a list of the errors, an empty list means there
    were no issues.
    """
    errors = []
    warnings = []
    df = pd.read_csv(file_fp, sep=delimiter, header=[0, 1])
    all_headers = []
    study_name = None
    tables = df.axes[1].levels[0].tolist()
    for j, table in enumerate(tables):
        table_df = df[table]
        for i, header in enumerate(table_df.axes[1]):
            col = table_df[header]
            col_index = len(all_headers)
            new_errors, new_warnings = check_column(col, col_index)
            errors += new_errors
            warnings += new_warnings

            all_headers.append(header)
            # Perform column specific checks
            if table == 'Specimen':
                if header == 'BarcodeSequence':
                    errors += check_duplicates(col, col_index)
                    errors += check_lengths(col, col_index)
                    errors += check_barcode_chars(col, col_index)
                elif header == 'SampleID':
                    errors += check_duplicates(col, col_index)
                elif header == 'LinkerPrimerSequence':
                    errors += check_lengths(col, col_index)
            elif study_name is None and table == 'Study':
                study_name = df[table]['StudyName'][i]
    missing_headers = REQUIRED_HEADERS.difference(set(all_headers))
    dups = check_duplicate_cols(all_headers)

    if len(dups) > 0:
        for dup in dups:
            locs = [i for i, header in enumerate(all_headers) if header == 'dup']
            for loc in locs:
                errors.append('1\t{}\tDuplicate header {}'.format(loc, dup))
    if missing_headers:
        errors.append('-1\t-1\tMissing requires fields: ' + ', '.join(missing_headers))

    return errors, warnings, study_name, df['Subjects']


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


def create_local_copy(fp, filename, path=STORAGE_DIR):
    """ Create a local copy of the file provided. """
    file_copy = join(path, 'copy_' + filename)
    # Write the data to a new file stored on the server
    with open(file_copy, 'wb') as nf:
        while True:
            data = fp.read(8192)
            nf.write(data)
            if not data:
                break
    return file_copy


def generate_error_html(file_fp, errors, warnings):
    """
    Generates an html page marking the errors and warnings found in
    the given metadata file.
    """
    df = pd.read_csv(file_fp, sep='\t', header=[0, 1])
    html = '<!DOCTYPE html><html>'
    html += '<link rel="stylesheet" href="/CSS/stylesheet.css">'
    markup = defaultdict(dict)
    top = []

    # Add Errors to markup table
    for error in errors:
        row, col, item = error.split('\t')
        if row == '-1' and col == '-1':
            top.append(['red', item])
        markup[int(row)][int(col)] = ['red', item]

    # Add warnings to markup table
    for warning in warnings:
        row, col, item = warning.split('\t')
        if row == '-1' and col == '-1':
            top.append(['yellow', item])
        markup[int(row)][int(col)] = ['yellow', item]

    # Add general warnings and errors
    for color, er in top:
        html += '<h3 style="color:{}">'.format(color) + er + '</h3>'

    # Get all the table and header names
    tables = []
    headers = []
    for (table, header) in df.axes[1]:
        tables.append(table)
        headers.append(header)

    # Create the table and header rows of the table
    html += '<table>'
    html += '<tr><th>' + '</th><th>'.join(tables) + '</th></tr>'
    html += '<tr><th>' + '</th><th>'.join(headers) + '</th></tr>'

    # Build each row of the table
    for row in range(len(df[tables[0]][headers[0]])):
        html += '<tr>'
        # Build each column in the row
        for col, (table, header) in enumerate(zip(tables, headers)):
            item = df[table][header][row]
            if table == 'Subjects':
                try_col = -2
            else:
                try_col = col
            # Add the error/warning if there is one
            try:
                color, issue = markup[row + 2][try_col]
                html += '<td bgcolor={}>{}<br>-----------<br>{}</td>'.format(color, item, issue)
            # Otherwise add the table item
            except KeyError:
                html += '<td>{}</td>'.format(item)
        html += '</tr>'
    html += '</table>'
    html += '</html>'
    return html
