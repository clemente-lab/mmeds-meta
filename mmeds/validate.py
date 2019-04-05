import pandas as pd
import mmeds.config as fig

from collections import defaultdict
from numpy import std, mean, issubdtype, number, datetime64, nan
from mmeds.util import log, load_ICD_codes, is_numeric, get_col_type


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

ILLEGAL_IN_HEADER = set('/\\ *?_')  # Limit to alpha numeric, dot, hyphen, has to start with alpha
ILLEGAL_IN_CELL = set(str(ILLEGAL_IN_HEADER))


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


def check_ICD_codes(column, col_index):
    """ Ensures all ICD codes in the column are valid. """
    # Load the ICD codes
    ICD_codes = load_ICD_codes()
    errors = []
    for i, cell in enumerate(column):
        if not pd.isnull(cell):
            parts = cell.split('.')
            if (ICD_codes.get(parts[0]) is None or ICD_codes.get(parts[0]).get(parts[1]) is None):
                errors.append('{}\t{}\tICD Code Error: Invalid ICD code {} in row {}'.format(i, col_index, cell, i))
    return errors


def validate_mapping_file(file_fp, delimiter='\t'):
    """
    Checks the mapping file at file_fp for any errors.
    Returns a list of the errors, an empty list means there
    were no issues.
    """
    valid = Validator(file_fp, sep=delimiter)
    return valid.run()


class Validator:

    def __init__(self, file_fp, sep):
        log('init validator')
        self.errors = []
        self.warnings = []
        self.study_name = 'NA'
        self.subjects = []
        self.tables = []
        self.all_headers = []
        self.file_fp = file_fp
        self.sep = sep
        self.df = pd.read_csv(file_fp,
                              sep=sep,
                              header=[0, 1],
                              skiprows=[2, 3, 4],
                              na_filter=False)
        self.df.replace('NA', nan, inplace=True)
        self.table_df = None

    def load_mapping_file(self, file_fp, delimiter):
        """
        Load the metadata file and assign datatypes to the columns
        ==========================================================
        :file_fp: The path to the mapping file
        :delimiter: The delimiter used in the mapping file
        """
        log('load_mapping_file')
        # Get the tables in the dataframe while maintaining order
        for (table, header) in self.df.axes[1]:
            log('checking types {}: {}'.format(table, header))
            self.tables.append(table)
            # Skip type checking for additional metadata
            if not table == 'AdditionalMetadata':
                for column in self.df[table]:
                    if '' in self.df[table][column]:
                        self.errors.append('-1\t-1\tColumn Value Error: Column {} is missing entries'.format(column))
                    try:
                        self.df[table].assign(column=self.df[table][column].astype(fig.COLUMN_TYPES[table][column]))
                    # Additional metadata won't have an entry so will automatically be treated as a string
                    except KeyError:
                        self.df[table].assign(column=self.df[table][column].astype('object'))
                    # Error handling for column values that don't match the column type
                    except ValueError:
                        err = '-1\t-1\tColumn Value Error: Column {} contains the wrong type of values'
                        self.errors.append(err.format(column))
        self.tables = list(dict.fromkeys(self.tables))

    def check_column(self, raw_column, col_index, is_additional=False):
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
        self.errors += check_header(header, col_index)

        # Check the remaining columns
        for i, cell in enumerate(column):
            cell_errors, cell_warnings = check_cell(i, col_index, cell, col_type, check_date, is_additional)
            self.errors += cell_errors
            self.warnings += cell_warnings

        # Ensure there is only one study being uploaded
        if header == 'StudyName' and len(set(column.tolist())) > 1:
            self.errors.append('-1\t-1\tMultiple Studies Error: Multiple studies in one metadata file')

        # Check that values fall within standard deviation
        if issubdtype(col_type, number) and not isinstance(raw_column.dtype, str):
            self.warnings += check_number_column(column, col_index, col_type)
        # Check for categorical data
        elif issubdtype(col_type, str) and not header == 'ICDCode':
            self.warnings += check_string_column(column, col_index)

    def check_table_column(self, name, header, col_index, row_index, study_name):
        log('Check table column: {}'.format(header))
        if not name == 'AdditionalMetaData' and header not in fig.TABLE_COLS[name]:
            if '.1' in header:
                err_message = '-1\t{}\tDuplicate Column Error: Duplicate of column {} in table {}'
                self.errors.append(err_message.format(col_index, header.replace('.1', ''), name))
            else:
                err_message = '-1\t{}\tColumn Table Error: Column {} should not be in table {}'
                self.errors.append(err_message.format(col_index, header, name))
        col = self.table_df[header]
        self.check_column(col, col_index, name == 'AdditionalMetaData')

        # Perform column specific checks
        if name == 'Specimen':
            if header == 'BarcodeSequence':
                self.errors += check_duplicates(col, col_index)
                self.errors += check_lengths(col, col_index)
                self.errors += check_barcode_chars(col, col_index)
            elif header == 'RawDataID':
                self.errors += check_duplicates(col, col_index)
            elif header == 'LinkerPrimerSequence':
                self.errors += check_lengths(col, col_index)
        elif name == 'ICDCode':
            self.errors += check_ICD_codes(col, col_index)
        elif study_name is None and name == 'Study':
            study_name = self.table_df['StudyName'][row_index]

    def check_table(self, name):
        """
        Check the data within a particular table
        ========================================
        :table_df: A pandas dataframe containing the data for the specified table
        :name: The name of the table
        :all_headers: The headers that have been encountered so far
        :study_name: None if no StudyName column has been seen yet,
            otherwise with have the previously seen StudyName
        """
        log('Check table: {}'.format(name))
        start_col = None
        end_col = None
        self.table_df = self.df[name]
        if not name == 'AdditionalMetaData':
            missing_cols = set(fig.TABLE_COLS[name]).difference(set(self.table_df.columns))
            if missing_cols:
                text = '-1\t-1\tMissing Column Error: Columns {} missing from table {}'
                self.errors.append(text.format(', '.join(missing_cols), name))
        # For each table column
        for i, header in enumerate(self.table_df.columns):
            # Check that end dates are after start dates
            if header == 'StartDate':
                start_col = i
            elif header == 'EndDate':
                end_col = i
            col_index = len(self.all_headers)
            self.check_table_column(name, header, col_index, i, self.study_name)
            self.all_headers.append(header)

        # Compare the start and end dates
        if start_col is not None and end_col is not None:
            self.check_dates()

    def check_dates(self):
        """
        Check that no dates in the end col are earlier than
        the matching date in the start col
        ===================================================
        :df: The data frame of the table containing the columns
        :table_col: The column of the offending start date:w
        """
        start_col = 0
        for i in range(len(self.df)):
            if self.df['StartDate'][i] > self.df['EndDate'][i]:
                err = '{}\t{}\tData Range Error: End date {} is earlier than start date {} in row {}'
                self.errors.append(err.format(i + 1, start_col, self.df['EndDate'][i], self.df['StartDate'][i], i))

    def run(self):
        log('In validate_mapping_file')
        self.load_mapping_file(self.file_fp, self.sep)

        all_headers = []
        # For each table
        for table in self.tables:
            # If the table shouldn't exist add and error and skip checking it
            if table not in fig.TABLE_ORDER:
                self.errors.append('-1\t-1\tTable Error: Table {} should not be the metadata'.format(table))
            else:
                self.check_table(table)

        # Check for duplicate columns
        dups = check_duplicate_cols(all_headers)
        if dups:
            for dup in dups:
                locs = [i for i, header in enumerate(all_headers) if header == 'dup']
                for loc in locs:
                    self.errors.append('1\t{}\tDuplicate Header Error: Duplicate header {}'.format(loc, dup))

        # Check for missing tables
        missing_tables = fig.METADATA_TABLES.difference(set(self.tables))
        if missing_tables:
            self.errors.append('-1\t-1\tMissing Table Error: Missing tables ' + ', '.join(missing_tables))

        # Check for missing headers
        missing_headers = REQUIRED_HEADERS.difference(set(all_headers))
        if missing_headers:
            self.errors.append('-1\t-1\tMissing Column Error: Missing required fields: ' + ', '.join(missing_headers))

        return self.errors, self.warnings, self.study_name, self.df['Subjects']
