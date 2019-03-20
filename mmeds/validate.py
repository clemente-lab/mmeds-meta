import pandas as pd
import mmeds.config as fig

from collections import defaultdict
from numpy import std, mean, issubdtype, number, datetime64
from mmeds.util import log, load_ICD_codes, is_numeric, load_mapping_file, get_col_type


NAs = ['n/a', 'n.a.', 'n_a', 'na', 'N/A', 'N.A.', 'N_A']

REQUIRED_HEADERS = set(['Description',
                        '#SampleID'
                        'BarcodeSequence'
                        'LinkerPrimerSequence'
                        'Lab'
                        'AnalysisTool'
                        'PrimaryInvestigator'])

REQUIRED_HEADERS = set(['SpecimenID', 'BarcodeSequence', 'PrimaryInvestigator'])

HIPAA_HEADERS = ['social_security', 'social_security_number', 'address', 'phone', 'phone_number']

DNA = set('GATC')

ILLEGAL_IN_HEADER = set('/\\ *?')  # Limit to alpha numeric, underscore, dot, hyphen, has to start with alpha
ILLEGAL_IN_CELL = set(str(ILLEGAL_IN_HEADER) + '_')


def check_header(header, col_index):
    """ Check the header field to ensure it complies with MMEDS requirements. """
    errors = []

    row_col = '0\t' + str(col_index) + '\t'

    # Check if it's numeric
    if is_numeric(header):
        text = 'Number Header Error: Column names cannot be numbers. Replace header %s of column\t%d '
        errors.append(row_col + text % (header, col_index))
    # Check if it's NA
    if header in NAs + ['NA']:
        errors.append(row_col + 'NA Header Error: Column names cannot be NA. Replace  header %s of column\t%d ' %
                      (header, col_index))
    # Check for illegal characters
    if ILLEGAL_IN_HEADER.intersection(set(header)):
        illegal_chars = ILLEGAL_IN_HEADER.intersection(set(header))
        err = 'Illegal Header Error: Illegal character(s) {}. Replace header {} of column {}'
        illegal = '({})'.format(','.join(illegal_chars).replace(' ', '<space>').replace('\t', '<tab>'))
        errors.append(row_col + err.format(illegal, header, col_index))
    # Check for HIPAA non-compliant headers
    if header.lower() in HIPAA_HEADERS:
        errors.append(row_col + 'PHI Header Error: Potentially identifying information in %s of column\t%d' %
                      (header, col_index))
    # Check for trailing or preceding whitespace
    if not header == header.strip():
        errors.append(row_col + 'Whitespace Header Error: Preceding or trailing whitespace %s in column %d' %
                      (header, col_index))
    return errors


def check_cell(row_index, col_index, cell, col_type, check_date, is_additional):
    """
    Check the data in the specified cell.
    ====================================
    :row_index: The index of the row of the cell
    :col_index: The index of the column of the cell
    :cell: The value of the cell
    :col_type: The known type of the column as a whole
    :check_date: If True check the cell for a valid date
    :is_additional: If true the column is additional metadata and there are fewer checks
    """
    errors = []
    warnings = []
    # An NA cell will not generate any errors
    if not cell == 'NA':
        row_col = str(row_index) + '\t' + str(col_index) + '\t'
        # Check for non-standard NAs
        if cell in NAs:
            errors.append(row_col + 'NA Error: Non standard NA format %s\t%d,%d' %
                          (cell, row_index, col_index))

        # Check for consistent types in the column
        if not issubdtype(col_type, datetime64):
            # If the cast fails for this cell the data must be the wrong type
            try:
                col_type(cell)
            except ValueError:
                message = 'Mixed Type {}: Value {} does not match column type {}'
                if is_additional:
                    warnings.append(row_col + message.format('Warning', cell, col_type))
                else:
                    errors.append(row_col + message.format('Error', cell, col_type))
        # Check for empty fields
        if '' == cell:
            errors.append(row_col + 'Empty Cell Error: Empty cell value %s' % cell)

        if isinstance(cell, str):
            # Check for trailing or preceding whitespace
            if not cell == cell.strip():
                errors.append(row_col + 'Whitespace Error: Preceding or trailing whitespace %s in row %d' %
                              (cell, row_index))
        # Check if this is the cell with the invalid date
        if check_date:
            try:
                pd.to_datetime(cell)
            except ValueError:
                errors.append(row_col + 'Date Error: Invalid date {} in row {}'.format(cell, row_index))
    return errors, warnings


def check_number_column(column, col_index, col_type):
    """ Check for mixed types and values outside two standard deviations. """
    warnings = []
    try:
        filtered = [col_type(x) for x in column.tolist() if not x == 'NA']
        stddev = std(filtered)
        avg = mean(filtered)
        for i, cell in enumerate(column):
            if not cell == 'NA' and (col_type(cell) > avg + (2 * stddev) or col_type(cell) < avg - (2 * stddev)):
                text = '%d\t%d\tStdDev Warning: Value %s outside of two standard deviations of mean in column %d'
                warnings.append(text % (i + 1, col_index, cell, col_index))
    except ValueError:
        warnings.append("-1\t-1\tMixed Type Warning: Cannot get average of column {}. Mixed types".format(column))
    return warnings


def check_string_column(column, col_index):
    """ Check for categorical data. """
    warnings = []
    counts = column.value_counts()
    stddev = std(counts.values)
    avg = mean(counts.values)
    for val, count in counts.iteritems():
        if count < (avg - stddev) and count < 3:
            text = '%d\t%d\tCategorical Data Warning: Potential categorical data detected.\
                Value %s may be in error, only %d found.'
            warnings.append(text % (-1, col_index, val, count))
    return warnings


def check_column(raw_column, col_index, is_additional=False):
    """
    Validate that there are no issues with the provided column of metadata.
    =======================================================================
    :raw_column: The unmodified column from the metadata dataframe
    :col_index: The index of the column in the original dataframe
    :is_additional: If true the column is additional metadata and there are fewer checks
    """
    column, col_type, check_date = get_col_type(raw_column)

    # Get the header
    header = column.name

    # Check the header
    errors = check_header(header, col_index)
    warnings = []

    # Check the remaining columns
    for i, cell in enumerate(column):
        cell_errors, cell_warnings = check_cell(i, col_index, cell, col_type, check_date, is_additional)
        errors += cell_errors
        warnings += cell_warnings

    # Ensure there is only one study being uploaded
    if header == 'StudyName' and len(set(column.tolist())) > 1:
        errors.append('-1\t-1\tMultiple Studies Error: Multiple studies in one metadata file')

    # Check that values fall within standard deviation
    if issubdtype(col_type, number) and not isinstance(raw_column.dtype, str):
        warnings += check_number_column(column, col_index, col_type)
    # Check for categorical data
    elif issubdtype(col_type, str) and not header == 'ICDCode':
        warnings += check_string_column(column, col_index)

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
    length = len(column[0])
    for i, cell in enumerate(column[1:]):
        if not len(cell) == length:
            errors.append('%d\t%d\tLength Error: Value %s has a different length from other values in column %d' %
                          (i + 1, col_index, cell, col_index))
    return errors


def check_barcode_chars(column, col_index):
    """ Check that BarcodeSequence only contains valid DNA characters. """
    errors = []
    for i, cell in enumerate(column):
        diff = set(cell).difference(DNA)
        if diff:
            errors.append('%d\t%d\tBarcode Error: Invalid BarcodeSequence char(s) %s in row %d' %
                          (i, col_index, ', '.join(diff), i))
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


def check_ICD_codes(column, col_index):
    """ Ensures all ICD codes in the column are valid. """
    # Load the ICD codes
    ICD_codes = load_ICD_codes()
    errors = []
    for i, cell in enumerate(column):
        if not pd.isnull(cell) and ICD_codes.get(cell) is None:
            errors.append('{}\t{}\tICD Code Error: Invalid ICD code {} in row {}'.format(i, col_index, cell, i))
    return errors


def check_table_column(table_df, name, header, col_index, row_index, study_name):
    errors = []
    warnings = []
    if not name == 'AdditionalMetaData' and header not in fig.TABLE_COLS[name]:
        if '.1' in header:
            err_message = '-1\t{}\tDuplicate Column Error: Duplicate of column {} in table {}'
            errors.append(err_message.format(col_index, header.replace('.1', ''), name))
        else:
            err_message = '-1\t{}\tColumn Table Error: Column {} should not be in table {}'
            errors.append(err_message.format(col_index, header, name))
    col = table_df[header]
    new_errors, new_warnings = check_column(col, col_index, name == 'AdditionalMetaData')
    errors += new_errors
    warnings += new_warnings

    # Perform column specific checks
    if name == 'Specimen':
        if header == 'BarcodeSequence':
            errors += check_duplicates(col, col_index)
            errors += check_lengths(col, col_index)
            errors += check_barcode_chars(col, col_index)
        elif header == 'RawDataID':
            errors += check_duplicates(col, col_index)
        elif header == 'LinkerPrimerSequence':
            errors += check_lengths(col, col_index)
    elif name == 'ICDCode':
        errors += check_ICD_codes(col, col_index)
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
        missing_cols = set(fig.TABLE_COLS[name]).difference(set(table_df.columns))
        if missing_cols:
            text = '-1\t-1\tMissing Column Error: Columns {} missing from table {}'
            errors.append(text.format(', '.join(missing_cols), name))
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
    log('In validate_mapping_file')
    tables, df, errors, warnings = load_mapping_file(file_fp, delimiter)

    all_headers = []
    study_name = None
    # For each table
    for table in tables:
        # If the table shouldn't exist add and error and skip checking it
        if table not in fig.TABLE_ORDER:
            errors.append('-1\t-1\tTable Error: Table {} should not be the metadata'.format(table))
        else:
            table_df = df[table]
            (new_errors, new_warnings, all_headers, study_name) = check_table(table_df, table, all_headers, study_name)
            errors += new_errors
            warnings += new_warnings
            log('table: {}, all_headers: {}'.format(table, all_headers))

    # Check for duplicate columns
    dups = check_duplicate_cols(all_headers)
    if dups:
        for dup in dups:
            locs = [i for i, header in enumerate(all_headers) if header == 'dup']
            for loc in locs:
                errors.append('1\t{}\tDuplicate Header Error: Duplicate header {}'.format(loc, dup))

    # Check for missing tables
    missing_tables = fig.METADATA_TABLES.difference(set(tables))
    if missing_tables:
        errors.append('-1\t-1\tMissing Table Error: Missing tables ' + ', '.join(missing_tables))

    # Check for missing headers
    missing_headers = REQUIRED_HEADERS.difference(set(all_headers))
    if missing_headers:
        errors.append('-1\t-1\tMissing Column Error: Missing required fields: ' + ', '.join(missing_headers))

    return errors, warnings, study_name, df['Subjects']
