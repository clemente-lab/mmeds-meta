from collections import defaultdict
from numpy import std, mean, issubdtype, number
from os.path import join, exists
from email.message import EmailMessage
from smtplib import SMTP
import mmeds.config as fig
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
    new_lines = lines[:line_number] + ['<h4><font color="red">' + error_message + '</font></h4>'] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def insert_warning(page, line_number, error_message):
    """ Inserts an error message in the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] + ['<h4><font color="orange">' + error_message + '</font></h4>'] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def insert_html(page, line_number, html):
    """
    Inserts additional HTML into the provided HTML page at the specified line number.
    =================================================================================
    :page: The page (a string) to insert the new HTML into
    :line_number: The line to insert the HTML
    :html: The HTML to insert
    """
    lines = page.split('\n')
    new_lines = lines[:line_number] + [html] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def check_header(header, col_index):
    """ Check the header field to ensure it complies with MMEDS requirements. """
    errors = []

    row_col = '0\t' + str(col_index) + '\t'

    # Check if it's numeric
    if is_numeric(header):
        errors.append(row_col + 'Number Header Error: Column names cannot be numbers. Replace header %s of column\t%d ' %
                      (header, col_index))
    # Check if it's NA
    if header in NAs + ['NA']:
        errors.append(row_col + 'NA Header Error: Column names cannot be NA. Replace  header %s of column\t%d ' %
                      (header, col_index))
    # Check for illegal characters
    if ILLEGAL_IN_HEADER.intersection(set(header)):
        illegal_chars = ILLEGAL_IN_HEADER.intersection(set(header))
        errors.append(row_col + 'Illegal Header Error: Illegal character(s) %s. Replace header %s of column\t%d' %
                      (' '.join(illegal_chars), header, col_index))
    # Check for HIPAA non-compliant headers
    if header.lower() in HIPAA_HEADERS:
        errors.append(row_col + 'PHI Header Error: Potentially identifying information in %s of column\t%d' %
                      (header, col_index))
    # Check for trailing or preceding whitespace
    if not header == header.strip():
        errors.append(row_col + 'Whitespace Header Error: Preceding or trailing whitespace %s in column %d' %
                      (header, col_index))
    return errors


def check_cell(row_index, col_index, cell, col_type, check_date):
    """
    Check the data in the specified cell.
    ====================================
    :row_index: The index of the row of the cell
    :col_index: The index of the column of the cell
    :cell: The value of the cell
    :col_type: The known type of the column as a whole
    :check_date: If True check the cell for a valid date
    """
    errors = []
    row_col = str(row_index) + '\t' + str(col_index) + '\t'
    # Check for non-standard NAs
    if cell in NAs:
        errors.append(row_col + 'NA Error: Non standard NA format %s\t%d,%d' %
                      (cell, row_index, col_index))

    # Check for consistent types in the column
    # Pandas stores 'str' as 'object' so check for that explicitly
    if (is_numeric(cell) and not issubdtype(col_type, number)) or\
       not col_type == type(cell) and\
       (not isinstance(cell, str) and 'object' == col_type):
        errors.append(row_col + 'Mixed Type Error: Mixed datatypes in column %d: %s' %
                      (col_index, cell))
    # Check for empty fields
    if '' == cell or pd.isnull(cell):
        errors.append(row_col + 'Empty Cell Error: Empty cell value %s' % cell)

    if type(cell) == str:
        if not cell == 'NA' and issubdtype(col_type, number):
            errors.append(row_col + 'Mixed Type Error: Mixed datatypes in column %d: %s' %
                          (col_index, cell))
        # Check for trailing or preceding whitespace
        if not cell == cell.strip():
            errors.append(row_col + 'Whitespace Error: Preceding or trailing whitespace %s in row %d' %
                          (cell, row_index))
    # Check if this is the cell with the invalid date
    if check_date:
        try:
            pd.to_datetime(cell)
        except ValueError:
            if not cell == 'NA':
                errors.append(row_col + 'Date Error: Invalid date {} in row {}'.format(cell, row_index))
    return errors


def get_col_type(raw_column):
    """
    Return the type of data the column should be checked for.
    =========================================================
    :raw_column: The column to check for type
    """
    check_date = False
    if 'Date' in raw_column.name:
        try:
            column = pd.to_datetime(raw_column)
        # If there is an error converting to datetime
        # check the individual cells
        except ValueError:
            column = raw_column
            check_date = True
    # Try to set the type based on the first non NA cell
    else:
        type_cell = raw_column[0]
        for cell in raw_column:
            if not cell == 'NA':
                type_cell = cell
                break
        try:
            column = raw_column.astype(type(type_cell))
        except ValueError:
            column = raw_column
    return column, check_date


def check_column(raw_column, col_index):
    """
    Validate that there are no issues with the provided column of metadata.
    =======================================================================
    :raw_column: The unmodified column from the metadata dataframe
    :col_index: The index of the column in the original dataframe
    """
    column, check_date = get_col_type(raw_column)

    # Get the header
    header = column.name

    # Check the header
    errors = check_header(header, col_index)
    warnings = []

    # Check the remaining columns
    for i, cell in enumerate(column):
        errors += check_cell(i, col_index, cell, column.dtype, check_date)

    # Ensure there is only one study being uploaded
    if header == 'StudyName' and len(set(column.tolist())) > 1:
        errors.append('-1\t-1\tMultiple Studies Error: Multiple studies in one metadata file')

    # Check that values fall within standard deviation
    if issubdtype(column.dtype, number):
        stddev = std(column)
        avg = mean(column)
        for i, cell in enumerate(column):
            if (cell > avg + (2 * stddev) or cell < avg - (2 * stddev)):
                warnings.append('%d\t%d\tStdDev Warning: Value %s outside of two standard deviations of mean in column %d' %
                                (i + 1, col_index, cell, col_index))
    # Check for catagorical data
    elif 'object' == column.dtype:
        counts = column.value_counts()
        stddev = std(counts.values)
        avg = mean(counts.values)
        for val, count in counts.iteritems():
            if count < (avg - stddev) and count < 3:
                warnings.append('%d\t%d\tCatagorical Data Warning: Potential catagorical data detected. Value %s may be in error, only %d found.' %
                                (-1, col_index, val, count))

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
            errors.append('%d\t%d\tDuplicate Value Error: Duplicate value of row %d, %s in row %d.' %
                          (val, col_index, value[0], dup_key, val))
    return errors


def check_lengths(column, col_index):
    """ Checks that all entries have the same length in the provided column """
    errors = []
    length = len(column[1])
    for i, cell in enumerate(column[2:]):
        if not len(cell) == length:
            errors.append('%d\t%d\tLength Error: Value %s has a different length from other values in column %d' %
                          (i + 2, col_index, cell, col_index))
    return errors


def check_barcode_chars(column, col_index):
    """ Check that BarcodeSequence only contains valid DNA characters. """
    errors = []
    for i, cell in enumerate(column[1:]):
        diff = set(cell).difference(DNA)
        if diff:
            errors.append('%d\t%d\tBarcode Error: Invalid BarcodeSequence char(s) %s in row %d' %
                          (i + 1, col_index, ', '.join(diff), i + 1))
    return errors


def check_duplicate_cols(headers):
    """
    Returns true if there are any duplicate headers.
    ================================================
    :headers: The headers for each column in the metadata file
    """
    dups = []
    for header in headers:
        if '.1' in header:
            dups.append(header.split('.')[0])
    return dups


def check_dates(df):
    """
    Check that no dates in the end col are earlier than
    the matching date in the start col
    ===================================================
    :df: The data frame of the table containing the columns
    :table_col: The column of the offending start date:w

    """
    errors = []
    start_col = 0
    for i in range(len(df)):
        if df['StartDate'][i] > df['EndDate'][i]:
            err = '{}\t{}\tData Range Error: End date {} is earlier than start date {} in row {}'
            errors.append(err.format(i + 1, start_col, df['EndDate'][i], df['StartDate'][i], i))
    return errors


def check_table_column(table_df, name, header, col_index, row_index, study_name):
    errors = []
    warnings = []
    if not name == 'AdditionalMetaData' and header not in fig.TABLE_COLS[name]:
        errors.append('-1\t{}\tColumn Table Error: Column {} should not be in table {}'.format(col_index, header, name))
    col = table_df[header]
    new_errors, new_warnings = check_column(col, col_index)
    errors += new_errors
    warnings += new_warnings

    # Perform column specific checks
    if name == 'Specimen':
        if header == 'BarcodeSequence':
            errors += check_duplicates(col, col_index)
            errors += check_lengths(col, col_index)
            errors += check_barcode_chars(col, col_index)
        elif header == 'SampleID':
            errors += check_duplicates(col, col_index)
        elif header == 'LinkerPrimerSequence':
            errors += check_lengths(col, col_index)
    elif study_name is None and name == 'Study':
        study_name = table_df['StudyName'][row_index]
    return errors, warnings


def check_table(table_df, name, all_headers, study_name):
    """
    Check the data within a particular table
    ========================================
    :table_df: A pandas dataframe containing the data for the specified table
    :name: The name of the table
    :all_headers: The headers that have been encountered so far
    :study_name: None if no StudyName column has been seen yet,
        otherwise with have the previously seen StudyName
    """
    errors = []
    warnings = []
    start_col = None
    end_col = None
    if not name == 'AdditionalMetaData':
        missing_cols = set(fig.TABLE_COLS[name]).difference(table_df.columns)
        if missing_cols:
            errors.append('-1\t-1\tMissing Column Error: Columns {} missing from table {}'.format(', '.join(missing_cols), name))
    # For each table column
    for i, header in enumerate(table_df.columns):
        # Check that end dates are after start dates
        if header == 'StartDate':
            start_col = i
        elif header == 'EndDate':
            end_col = i
        col_index = len(all_headers)
        new_errors, new_warnings = check_table_column(table_df,
                                                      name,
                                                      header,
                                                      col_index,
                                                      i,
                                                      study_name)
        all_headers.append(header)
        errors += new_errors
        warnings += new_warnings
    # Compare the start and end dates
    if start_col is not None and end_col is not None:
        errors += check_dates(table_df)
    return (errors, warnings, all_headers, study_name)


def validate_mapping_file(file_fp, delimiter='\t'):
    """
    Checks the mapping file at file_fp for any errors.
    Returns a list of the errors, an empty list means there
    were no issues.
    """
    errors = []
    warnings = []
    df = pd.read_csv(file_fp, sep=delimiter, header=[0, 1], na_filter=False)
    # Get the tables in the dataframe while maintaining order
    tables = []
    for (table, header) in df.axes[1]:
        tables.append(table)
    tables = list(dict.fromkeys(tables))

    all_headers = []
    study_name = None
    # For each table
    for table in tables:
        # If the table shouldn't exist add and error and skip checking it
        if table not in fig.TABLE_ORDER:
            errors.append('-1\t-1\tTable Error: Table {} should not be the metadata'.format(table))
            continue
        table_df = df[table]
        (new_errors,
         new_warnings,
         all_headers,
         study_name) = check_table(table_df, table, all_headers, study_name)
        errors += new_errors
        warnings += new_warnings

    # Check for duplicate columns
    dups = check_duplicate_cols(all_headers)
    if len(dups) > 0:
        for dup in dups:
            locs = [i for i, header in enumerate(all_headers) if header == 'dup']
            for loc in locs:
                errors.append('1\t{}\tDuplicate Header Error: Duplicate header {}'.format(loc, dup))

    # Check for missing tables
    missing_tables = set(fig.TABLE_ORDER).difference(set(tables))
    if missing_tables:
        errors.append('-1\t-1\tMissing Table Error: Missing tables ' + ', '.join(missing_tables))

    # Check for missing headers
    missing_headers = REQUIRED_HEADERS.difference(set(all_headers))
    if missing_headers:
        errors.append('-1\t-1\tMissing Column Error: Missing required fields: ' + ', '.join(missing_headers))

    return errors, warnings, study_name, df['Subjects']


def is_numeric(s):
    """
    Check if the provided string is a number.
    =========================================
    :s: The string to check
    """
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        pass
    try:
        import unicodedata
        unicodedata.numeric(s)
        return True
    except (TypeError, ValueError):
        pass
    return False


def create_local_copy(fp, filename, path=fig.STORAGE_DIR):
    """ Create a local copy of the file provided. """
    # Create the filename
    file_copy = join(path, '_'.join(['copy', fig.get_salt(5), filename]))
    # Ensure there is not already a file with the same name
    while exists(file_copy):
        file_copy = join(path, '_'.join(['copy', fig.get_salt(5), filename]))

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
    ===============================================================
    :file_fp: The destination the error file will be written to
    :errors: A list of the errors the metadata file produced
    :warnings: A list of the warnings the metadata file produced
    """
    df = pd.read_csv(file_fp, sep='\t', header=[0, 1])
    html = '<!DOCTYPE html>\n<html>\n'
    html += '<link rel="stylesheet" href="/CSS/stylesheet.css">\n'
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
        html += '<h3 style="color:{}">'.format(color) + er + '</h3>\n'

    # Get all the table and header names
    tables = []
    headers = []
    for (table, header) in df.axes[1]:
        tables.append(table)
        headers.append(header)

    # Create the table and header rows of the table
    html += '<table>'
    html += '<tr><th>' + '</th>\n<th>'.join(tables) + '</th>\n</tr>'
    html += '<tr><th>' + '</th>\n<th>'.join(headers) + '</th>\n</tr>'

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
                html += '<td style="color:black" bgcolor={}>{}<div style="font-weight:bold"><br>-----------<br>{}</div></td>\n'.format(color, item, issue)
            # Otherwise add the table item
            except KeyError:
                html += '<td style="color:black">{}</td>\n'.format(item)
        html += '</tr>\n'
    html += '</table>\n'
    html += '</html>\n'
    return html


def send_email(toaddr, user, message='upload', **kwargs):
    """
    Sends a confirmation email to addess containing user and code.
    ==============================================================
    :toaddr: The address to send the email to
    :user: The user account that toaddr belongs to
    :message: The type of message to send
    :kwargs: Any information that is specific to a paricular message type
    """
    msg = EmailMessage()
    msg['From'] = fig.MMEDS_EMAIL
    msg['To'] = toaddr
    if message == 'upload':
        body = 'Hello {email},\nthe user {user} uploaded data to the mmeds database server.\n'.format(email=toaddr, user=user) +\
               'In order to gain access to this data without the password to\n{user} you must provide '.format(user=user) +\
               'the following access code:\n{code}\n\nBest,\nMmeds Team\n\n'.format(code=kwargs['code']) +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'.format(cemail=fig.CONTACT_EMAIL)
        msg['Subject'] = 'New data uploaded to mmeds database'
    elif message == 'reset':
        body = 'Hello {},\nYour password has been reset.\n'.format(toaddr) +\
               'The new password is:\n{}\n\nBest,\nMmeds Team\n\n'.format(kwargs['password']) +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(fig.CONTACT_EMAIL)
        msg['Subject'] = 'Password Reset'
    elif message == 'change':
        body = 'Hello {},\nYour password has been changed.\n'.format(toaddr) +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(fig.CONTACT_EMAIL)
        msg['Subject'] = 'Password Change'
    elif message == 'analysis':
        body = 'Hello {},\nYour requested {} analysis on study {} is complete.\n'.format(toaddr,
                                                                                         kwargs['analysis_type'],
                                                                                         kwargs['study_name']) +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {} with a description of your problem.\n'.format(fig.CONTACT_EMAIL)
        msg['Subject'] = 'Analysis Complete'

    msg.set_content(body)

    server = SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(fig.MMEDS_EMAIL, 'mmeds_server')
    server.send_message(msg)
    server.quit()
