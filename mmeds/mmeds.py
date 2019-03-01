from collections import defaultdict
from numpy import std, mean, issubdtype, number, nan
from numpy import datetime64
from mmeds.error import MetaDataError, InvalidConfigError, InvalidSQLError, InvalidModuleError
from subprocess import run
from datetime import datetime
from pathlib import Path
from os import environ
import mmeds.config as fig
import pandas as pd
import numpy as np

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


def load_config(config_file, metadata):
    """ Read the provided config file to determine settings for the analysis. """
    config = {}
    # If no config was provided load the default
    if config_file is None:
        log('Using default config')
        with open(fig.STORAGE_DIR / 'config_file.txt', 'r') as f:
            page = f.read()
    else:
        # Load the file contents
        page = config_file

    # Parse the config
    lines = page.split('\n')
    for line in lines:
        if line.startswith('#') or line == '':
            continue
        else:
            parts = line.split('\t')
            if parts[0] not in fig.CONFIG_PARAMETERS:
                raise InvalidConfigError('Invalid parameter {} in config file'.format(parts[0]))
            config[parts[0]] = parts[1]
    try:
        # Parse the values/levels to be included in the analysis
        for option in fig.CONFIG_PARAMETERS:
            # Get approriate metadata columns based on the metadata file
            if option == 'metadata':
                config[option], config['metadata_continuous'] = get_valid_columns(metadata, config[option])
            # Split taxa_levels into a list or create the list if 'all'
            elif option == 'taxa_levels':
                if config[option] == 'all':
                    config[option] = [i + 1 for i in range(7)]
                else:
                    # Otherwise split the values into a list
                    config[option] = config[option].split(',')
            # Otherwise just ensure the parameter exists.
            else:
                assert config[option]
    except (KeyError, AssertionError):
        raise InvalidConfigError('Missing parameter {} in config file'.format(option))

    return config


def get_valid_columns(metadata_file, option):
    """
    Get the column headers for metadata columns meeting the
    criteria to be used in analysis.
    =======================================================
    :metadata_file: Path to the metadata file for this analysis.
    :option: A string. Either a comma separated list of columns or 'all' for all columns
    Returns:
        :summary_cols: A list of columns that are valid for summary analysis
        :col_types: A dictionary with the values of summary_cols as keys.
            True indicates that the column contains continuous values.
            False indicates that it contains discrete value.
    """
    summary_cols = []
    col_types = {}
    # Filter out any categories containing only NaN
    # Or containing only a single metadata value
    # Or where every sample contains a different value
    df = pd.read_csv(metadata_file, header=0, skiprows=[0, 2, 3, 4], sep='\t')
    if option == 'all':
        cols = df.columns
        #summary_cols += ['Separate', 'Together']
        #col_types.update({'Separate': False, 'Together': False})
    else:
        cols = option.split(',')
    # Ensure there aren't any invalid columns specified to be included in the analysis
    try:
        for col in cols:
            # If 'all' only select columns that don't have all the same or all unique values
            if (df[col].isnull().all() or df[col].nunique() == 1 or df[col].nunique() == len(df[col])):
                if option == 'all':
                    continue
                else:
                    raise InvalidConfigError('Invalid metadata column {} selected for analysis'.format(col))
            # If the columns is explicitly specified only check that it exists in the metadata
            else:
                assert df[col].any()
                summary_cols.append(col)
                col_types[col] = pd.api.types.is_numeric_dtype(df[col])
    except KeyError:
        raise InvalidConfigError('Invalid metadata column {} in config file'.format(col))
    return summary_cols, col_types


def load_ICD_codes():
    """ Load all known ICD codes and return them as a dictionary """
    ICD_codes = {'XXX.XXXX': 'Subject is healthy to the best of our knowledge'}
    with open(fig.STORAGE_DIR / 'icd10cm_codes_2018.txt') as f:
        # Parse each line
        for line in f:
            parts = line.split(' ')
            # Code is first part
            code = parts[0]
            # Description is second
            description = ' '.join(parts[1:]).strip()
            # Fill in codes with 'X'
            while len(code) < 7:
                code += 'X'
            code = code[:3] + '.' + code[3:]
            ICD_codes[code] = description
    return ICD_codes


def insert_error(page, line_number, error_message):
    """ Inserts an error message in the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] + ['<h4><font color="red">' + error_message + '</font></h4>'] + lines[line_number:]
    new_page = '\n'.join(new_lines)
    return new_page


def insert_warning(page, line_number, error_message):
    """ Inserts an error message in the provided HTML page at the specified line number. """
    lines = page.split('\n')
    new_lines = lines[:line_number] +\
        ['<h4><font color="orange">' + error_message + '</font></h4>'] +\
        lines[line_number:]
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


def load_html(file_path, **kwargs):
    """
    Load the specified html file. Inserting the head and topbar
    """
    # Load the html page
    with open(fig.HTML_DIR / (file_path + '.html')) as f:
        page = f.read().split('\n')

    # Load the head information
    with open(fig.HTML_DIR / 'header.html') as f:
        header = f.read().split('\n')

    # Load the topbar information
    with open(fig.HTML_DIR / 'topbar.html') as f:
        topbar = f.read().split('\n')

    new_page = page[:2] + header + topbar + page[2:]
    return '\n'.join(new_page).format(**kwargs)


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
    # An NA cell will not generate any errors
    if cell == 'NA':
        return []
    errors = []
    row_col = str(row_index) + '\t' + str(col_index) + '\t'
    # Check for non-standard NAs
    if cell in NAs:
        errors.append(row_col + 'NA Error: Non standard NA format %s\t%d,%d' %
                      (cell, row_index, col_index))

    # Check for consistent types in the column
    if not (issubdtype(col_type, datetime64) or issubdtype(col_type, object)):
        # If the cast fails for this cell the data must be the wrong type
        try:
            col_type(cell)
        except ValueError:
            errors.append(row_col + 'Mixed Type Error: Value {} does not match column type {}'.format(cell, col_type))
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
    return errors


def get_col_type(raw_column):
    """
    Return the type of data the column should be checked for.
    =========================================================
    :raw_column: The column to check for type
    """
    check_date = False
    col_type = None
    if 'Date' in raw_column.name:
        col_type = datetime64
        try:
            column = pd.to_datetime(raw_column)
        # If there is an error converting to datetime
        # check the individual cells
        except ValueError:
            column = raw_column
            check_date = True
    # Try to set the type based on the most common type
    else:
        column = raw_column
        types = {
            int: 0,
            float: 0,
            str: 0
        }

        for cell in raw_column:
            # Don't count NA
            if cell == 'NA':
                continue
            # Check if value is numeric
            elif is_numeric(cell):
                try:
                    int(cell)
                    types[int] += 1
                except ValueError:
                    types[float] += 1
            # Check if it's a string
            else:
                try:
                    str(cell)
                    types[str] += 1
                except TypeError:
                    continue
        col_type = max(types, key=types.get)
    return column, col_type, check_date


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


def check_column(raw_column, col_index):
    """
    Validate that there are no issues with the provided column of metadata.
    =======================================================================
    :raw_column: The unmodified column from the metadata dataframe
    :col_index: The index of the column in the original dataframe
    """
    column, col_type, check_date = get_col_type(raw_column)

    # Get the header
    header = column.name

    # Check the header
    errors = check_header(header, col_index)
    warnings = []

    # Check the remaining columns
    for i, cell in enumerate(column):
        errors += check_cell(i, col_index, cell, col_type, check_date)

    # Ensure there is only one study being uploaded
    if header == 'StudyName' and len(set(column.tolist())) > 1:
        errors.append('-1\t-1\tMultiple Studies Error: Multiple studies in one metadata file')

    # Check that values fall within standard deviation
    if issubdtype(col_type, number) and not isinstance(raw_column.dtype, object):
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
        if ICD_codes.get(cell) is None:
            errors.append('{}\t{}\tICD Code Error: Invalid ICD code {} in row {}'.format(i, col_index, cell, i))
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
        missing_cols = set(fig.TABLE_COLS[name]).difference(table_df.columns)
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


def load_mapping_file(file_fp, delimiter):
    """
    Load the metadata file and assign datatypes to the columns
    ==========================================================
    :file_fp: The path to the mapping file
    :delimiter: The delimiter used in the mapping file
    """
    df = pd.read_csv(file_fp,
                     sep=delimiter,
                     header=[0, 1],
                     skiprows=[2, 3, 4],
                     na_filter=False)
    df.replace('NA', nan, inplace=True)
    # Get the tables in the dataframe while maintaining order
    tables = []
    for (table, header) in df.axes[1]:
        tables.append(table)
        for column in df[table]:
            try:
                df[table].assign(column=df[table][column].astype(fig.COLUMN_TYPES[table][column]))
            except KeyError:
                df[table].assign(column=df[table][column].astype('object'))
    tables = list(dict.fromkeys(tables))
    return tables, df


def validate_mapping_file(file_fp, delimiter='\t'):
    """
    Checks the mapping file at file_fp for any errors.
    Returns a list of the errors, an empty list means there
    were no issues.
    """
    log('In validate_mapping_file')
    errors = []
    warnings = []
    tables, df = load_mapping_file(file_fp, delimiter)

    all_headers = []
    study_name = None
    # For each table
    for table in tables:
        # If the table shouldn't exist add and error and skip checking it
        if table not in fig.TABLE_ORDER:
            errors.append('-1\t-1\tTable Error: Table {} should not be the metadata'.format(table))
            continue
        table_df = df[table]
        (new_errors, new_warnings, all_headers, study_name) = check_table(table_df, table, all_headers, study_name)
        errors += new_errors
        warnings += new_warnings

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


def is_numeric(s):
    """
    Check if the provided string is a number.
    =========================================
    :s: The string to check
    """
    if issubdtype(type(s), str):
        if ('.e' in s or '.E' in s):
            return False
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
    log("In create_local_copy.")
    # If the fp is None return None
    if fp is None:
        return None

    # Create the filename
    file_copy = Path(path) / Path(filename).name

    # Ensure there is not already a file with the same name
    while file_copy.is_file():
        file_copy = Path(path) / '_'.join([fig.get_salt(5), filename])
    log('Created filepath {}'.format(file_copy))

    # Write the data to a new file stored on the server
    with open(file_copy, 'wb') as nf:
        while True:
            data = fp.read(8192)
            nf.write(data)
            if not data:
                break
    log('Copy finished')
    return str(file_copy)


def build_error_rows(df, tables, headers, markup):
    html = ''
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
                color, issue = markup[row + 4][try_col]
                html += '<td style="color:black" bgcolor="{}">\
                    {}<div style="font-weight:bold">\
                    <br>-----------<br>{}</div></td>\n'.format(color, item, issue)
            # Otherwise add the table item
            except KeyError:
                html += '<td style="color:black">{}</td>\n'.format(item)
        html += '</tr>\n'
    return html


def generate_error_html(file_fp, errors, warnings):
    """
    Generates an html page marking the errors and warnings found in
    the given metadata file.
    ===============================================================
    :file_fp: The original metadata file
    :errors: A list of the errors the metadata file produced
    :warnings: A list of the warnings the metadata file produced
    """
    df = pd.read_csv(file_fp, sep='\t', header=[0, 1], skiprows=[2, 3, 4])
    html = '<!DOCTYPE html>\n<html>\n'
    html += '<link type="text/javascript" rel="stylesheet" href="/CSS/stylesheet.css">\n'
    html += '<title> MMEDS Metadata Errors </title>\n'
    html += '<body>'
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
    # Fill out the table
    html += build_error_rows(df, tables, headers, markup)
    html += '</table>\n</body>\n</html>'
    return html


def split_data(column):
    """
    Split the data into multiple columns
    ------------------------------------
    :column: A pandas Series object
    """
    result = defaultdict(list)
    if column.name == 'lat_lon':
        for value in column:
            parsed = value.strip('+').split('-')
            result['Latitude'].append(parsed[0])
            result['Longitude'].append(parsed[1])
    elif column.name == 'assembly_name':
        for value in column:
            parsed = value.strip(' ')
            result['Tool'].append(parsed[0])
            result['Version'].append(parsed[1])
    else:
        raise ValueError
    return result


def load_MIxS_metadata(file_fp, skip_rows, unit_column):
    """
    A function for load and transforming the MIxS data in a pandas dataframe.
    ========================================================================
    :file_fp: The path to the file to convert
    :skip_rows: The number of rows to skip after the header
    :unit_column: A string. If None then the function checks each cell for units.
    """
    # Read in the data file
    df = pd.read_csv(file_fp, header=0, sep='\t')
    # Set the index to be the 'column_header' column
    df.set_index('column_header', inplace=True)
    # Remove rows with null indexes
    df = df.loc[df.index.notnull()]
    # Retrieve the unit column if one is specified
    if unit_column is not None:
        try:
            units = df[unit_column]
            df.drop(unit_column, axis=1, inplace=True)
        except KeyError:
            raise MetaDataError('The provided unit column is invalid.')
    else:
        units = {}
    # Transpose the dataframe across the diagonal
    df = df.T
    # Drop unnamed columns
    df.drop([x for x in df.axes[0] if 'Unnamed' in x], inplace=True)
    # Drop any columns with only np.nan values
    df.dropna(how='all', axis='columns', inplace=True)
    # Replace np.nans with "NA"s
    df.fillna('"NA"', inplace=True)
    return df, units


def MIxS_to_mmeds(file_fp, out_file, skip_rows=0, unit_column=None):
    """
    A function for converting a MIxS formatted datafile to a MMEDS formatted file.
    ------------------------------------------------------------------------------
    :file_fp: The path to the file to convert
    :out_file: The path to write the new metadata file to
    :skip_rows: The number of rows to skip after the header
    :unit_column: A string. If None then the function checks each cell for units.
    """

    df, units = load_MIxS_metadata(file_fp, skip_rows, unit_column)

    # Create a new dictionary for accessing the columns belonging to each table
    all_cols = defaultdict(list)
    all_cols.update(fig.METADATA_COLS)

    # Find all columns that don't have a mapping and add them to AdditionalMetaData
    unmapped_items = [x for x in df.columns if fig.MMEDS_MAP.get(x) is None]
    for item in unmapped_items:
        # If there is no units entry for the item
        if pd.isnull(units.get(item)):
            first = df[item][0].split(' ')
            # If the value is numeric grab the units in the data cell
            if is_numeric(first[0]):
                unit_col = item  # + ' ({})'.format(' '.join(first[1:]))
                df[item] = df[item].map(lambda x: x.split(' ')[0])
            else:
                unit_col = item
        # Add the units to the header if available
        else:
            unit_col = item  # + ' ({})'.format(units[item])
        fig.MIXS_MAP[('AdditionalMetaData', str(unit_col))] = str(unit_col)
        fig.MMEDS_MAP[item] = ('AdditionalMetaData', str(unit_col))
        all_cols['AdditionalMetaData'].append(str(unit_col))

    # Build the data for the new format
    meta = {}
    for col in df.columns:
        (table, column) = fig.MMEDS_MAP[col]
        if ':' in column:
            cols = column.split(':')
            data = split_data(df[col])
            for new_col in cols:
                meta[(table, new_col)] = data[new_col]
        else:
            meta[(table, column)] = df[col].astype(str)

    # Write the file
    write_mmeds_metadata(out_file, meta, all_cols, len(df))


def write_mmeds_metadata(out_file, meta, all_cols, num_rows):
    """
    Write out a mmeds metadate file based on the data provided
    ----------------------------------------------------------
    :out_file: The path to write the metadata to
    :meta: A dictionary containing all the information to write
    :all_cols: A dictionary specifying all the tables and columns
        for this metadata file
    :num_rows: An int. The number of rows in the original metadata
    """

    # Build the first two rows of the mmeds metadata file
    table_row, column_row = [], []
    for table in sorted(all_cols.keys()):
        for column in sorted(all_cols[table]):
            table_row.append(table)
            column_row.append(column.strip(' ()'))

    # Get the additional header rows from one of the example metadata files
    md_template = pd.read_csv(fig.TEST_METADATA, sep='\t', header=[0, 1], nrows=5, na_filter=False)
    column_type = []
    column_unit = []
    column_required = []
    for (table, column) in zip(table_row, column_row):
        try:
            column_type.append(str(md_template[table][column].iloc[0]))
            column_unit.append(str(md_template[table][column].iloc[1]))
            column_required.append(str(md_template[table][column].iloc[2]))
        except KeyError:
            column_type.append('')
            column_unit.append('')
            column_required.append('')

    # Write out each line of the file
    with open(out_file, 'w') as f:
        f.write('\t'.join(table_row) + '\n')
        f.write('\t'.join(column_row) + '\n')
        f.write('\t'.join(column_type) + '\n')
        f.write('\t'.join(column_unit) + '\n')
        f.write('\t'.join(column_required) + '\n')
        for i in range(num_rows):
            row = []
            for table, column in zip(table_row, column_row):
                # Add the value to the row
                try:
                    row.append(meta[(table, column)][i])
                # If a value doesn't exist for this table,column insert NA
                except KeyError:
                    row.append('"NA"')
            f.write('\t'.join(row) + '\n')


def mmeds_to_MIxS(file_fp, out_file, skip_rows=0, unit_column=None):
    """
    A function to convert a mmeds formatted metadata file to a MIxS one.
    """
    # Read in the data file
    df = pd.read_csv(file_fp, header=[0, 1], skiprows=[2, 3, 4], sep='\t')
    with open(out_file, 'w') as f:
        f.write('\t'.join(['column_header'] + list(map(str, df['RawData']['RawDataID'].tolist()))) + '\n')
        for (col1, col2) in df.columns:
            if df[col1][col2].notnull().any():
                try:
                    header = fig.MIXS_MAP[(col1, col2)]
                except KeyError:
                    header = col2
                f.write('\t'.join([header] + list(map(str, df[col1][col2].tolist()))) + '\n')


def log(text):
    """ Write provided text to the log file. """
    if isinstance(text, dict):
        log_text = '\n'.join(["{}: {}".format(key, value) for (key, value) in text.items()])
    elif isinstance(text, list):
        log_text = '\n'.join(list(map(str, text)))
    else:
        log_text = str(text)
    with open(fig.MMEDS_LOG, 'a+') as f:
        f.write('{}: {}\n'.format(datetime.now(), log_text))


def send_email(toaddr, user, message='upload', testing=False, **kwargs):
    """
    Sends a confirmation email to addess containing user and code.
    ==============================================================
    :toaddr: The address to send the email to
    :user: The user account that toaddr belongs to
    :message: The type of message to send
    :kwargs: Any information that is specific to a paricular message type
    """
    log('Send email to: {} on behalf of {}'.format(toaddr, user))
    if testing:
        return
    for key in kwargs.keys():
        log('{}: {}'.format(key, kwargs[key]))

    # Templates for the different emails mmeds sends
    if message == 'upload':
        body = 'Hello {email},\nthe user {user} uploaded data to the mmeds database server.\n' +\
               'In order to gain access to this data without the password to\n{user} you must provide ' +\
               'the following access code:\n{code}\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'New Data Uploaded'
    elif message == 'reset':
        body = 'Hello {user},\nYour password has been reset.\n' +\
               'The new password is:\n{password}\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {contact} with a description of your problem.\n'
        subject = 'Password Reset'
    elif message == 'change':
        body = 'Hello {user},\nYour password has been changed.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Password Change'
    elif message == 'analysis':
        body = 'Hello {user},\nYour requested {analysis} analysis on study {study} is complete.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Analysis Complete'
    elif message == 'error':
        body = 'Hello {user},\nThere was an error during requested {analysis} analysis.\n' +\
               'Please check the error file associated with this study.\n' +\
               'If you did not do this contact us immediately.\n\nBest,\nMmeds Team\n\n' +\
               'If you have any issues please email: {cemail} with a description of your problem.\n'
        subject = 'Error During Analysis'

    email_body = body.format(
        user=user,
        cemail=fig.CONTACT_EMAIL,
        email=toaddr,
        analysis=kwargs.get('analysis_type'),
        study=kwargs.get('study_name'),
        code=kwargs.get('code'),
        password=kwargs.get('password')
    )
    script = 'echo "{body}" | mail -s "{subject}" "{toaddr}"'
    if 'summary' in kwargs.keys():
        script += ' -A {summary}'.format(kwargs['summary'])
    cmd = script.format(body=email_body, subject=subject, toaddr=toaddr)
    log(cmd)
    run(['/bin/bash', '-c', cmd], check=True)


def pyformat_translate(value):
    """ Convert from numpy to standard python datatypes. """
    if isinstance(value, np.int64):
        result = int(value)
    elif isinstance(value, np.float64):
        result = float(value)
    else:
        result = value
    return result


def setup_environment(module):
    """
    Returns a dictionary with the environment variables loaded for a particular module.
    ===================================================================================
    :module: A string. The name of the module to load.
    """
    # Check there is nothing in module that could cause problems
    if not module.replace('_', '').replace('-', '').isalnum():
        raise InvalidModuleError('{} is not a valid module name.' +
                                 'Modules may only contain letters, numbers, "_", and "-"')

    log('Setup environment for {}'.format(module))
    run(['/bin/bash', '-c', 'module use ~/.modules/modulefiles'], check=True)
    new_env = environ.copy()
    output = run(['/bin/bash', '-c', 'module load {}; echo $PATH;'.format(module)],
                 capture_output=True, env=new_env, check=True)
    new_env['PATH'] = output.stdout.decode('utf-8').strip()
    log('New path: {}'.format(new_env['PATH']))
    return new_env


def create_qiime_from_mmeds(mmeds_file, qiime_file):
    """
    Create a qiime mapping file from the mmeds metadata
    ===================================================
    :mmeds_file: The path to the mmeds metadata.
    :qiime_file: The path where the qiime mapping file should be written.
    """
    mdata = pd.read_csv(mmeds_file, header=1, skiprows=[2, 3, 4], sep='\t')
    #mdata = mdata.assign(Together=['All' for x in range(len(mdata))],
    #                     Separate=mdata['RawDataID'])

    headers = list(mdata.columns)

    di = headers.index('RawDataID')
    hold = headers[0]
    headers[0] = '#SampleID'
    headers[di] = hold

    di = headers.index('SampleID')
    hold = headers[3]
    headers[3] = 'MmedsSampleID'
    headers[di] = hold

    hold = headers[1]
    di = headers.index('BarcodeSequence')
    headers[1] = 'BarcodeSequence'
    headers[di] = hold

    hold = headers[2]
    di = headers.index('LinkerPrimerSequence')
    headers[2] = 'LinkerPrimerSequence'
    headers[di] = hold

    hold = headers[-1]
    di = headers.index('Description')
    headers[-1] = 'Description'
    headers[di] = hold

    with open(qiime_file, 'w') as f:
        f.write('\t'.join(headers) + '\n')
        for row_index in range(len(mdata)):
            row = []
            for header in headers:
                if header == '#SampleID':
                    row.append(str(mdata['RawDataID'][row_index]))
                elif header == 'MmedsSampleID':
                    row.append(str(mdata['SampleID'][row_index]))
                else:
                    row.append(str(mdata[header][row_index]))
            f.write('\t'.join(row) + '\n')
    return list(mdata.columns)


def quote_sql(sql, **kwargs):
    """ Returns the sql query with the identifiers properly qouted using `"""
    quoted_args = {}
    for key, item in kwargs.items():
        # Check the entry is a string
        if not isinstance(item, str):
            raise InvalidSQLError('SQL Identifier {} is not a string'.format(item))
        # Check the entry isn't too long
        elif len(item) > 66:
            raise InvalidSQLError('SQL Identifier {} is too long ( > 66 characters)'.format(item))
        # Check that there are only allowed characters: Letters, Numbers, and '_'
        elif not item.replace('_', '').isalnum():
            raise InvalidSQLError('Illegal characters in identifier {}.' +
                                  ' Only letters, numbers, and "_" are permitted'.format(item))

        quoted_args[key] = '`{}`'.format(item)
    formatted = sql.format(**quoted_args)
    return formatted
