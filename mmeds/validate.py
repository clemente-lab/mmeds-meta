import pandas as pd
import mmeds.config as fig
import re

from collections import defaultdict
from numpy import std, mean, issubdtype, number, datetime64
from mmeds.util import log, load_ICD_codes, is_numeric, load_metadata
from mmeds.error import InvalidMetaDataFileError


NAs = ['n/a', 'n.a.', 'n_a', 'na', 'N/A', 'N.A.', 'N_A']

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
    Returns a list of the errors and warnings,
    an empty list means there were no issues.
    """
    valid = Validator(file_fp, sep=delimiter)
    return valid.run()


class Validator:

    def __init__(self, file_fp, sep):
        """ Initialize the validator object. """

        log('init validator')
        self.errors = []
        self.warnings = []
        self.study_name = 'NA'
        self.subjects = []
        self.file_fp = file_fp
        self.sep = sep
        log(file_fp)
        self.header_df = None
        log(self.header_df)
        self.df = None
        self.tables = []
        self.columns = []

        self.col_types = {}
        self.table_df = None
        self.cur_col = None    # Current column being checked
        self.cur_row = 0       # Current row being checked
        self.cur_table = None  # Current table being checked

        self.seen_tables = []
        self.seen_cols = []

    def load_mapping_file(self, file_fp, delimiter):
        """
        Load the metadata file and assign datatypes to the columns
        ==========================================================
        :file_fp: The path to the mapping file
        :delimiter: The delimiter used in the mapping file
        """
        log('load_mapping_file')
        try:
            self.df = load_metadata(self.file_fp)
            self.header_df = pd.read_csv(self.file_fp,
                                         sep=self.sep,
                                         header=[0, 1],
                                         nrows=3)
        except pd.errors.ParserError:
            raise InvalidMetaDataFileError('There is an issue parsing your metadata. Please check that it is in' +
                                           ' tab delimited format with no tab or newline characters in any of the' +
                                           'cells')
        # Setup the tables and columns
        for table, column in self.df.columns:
            if table not in self.tables:
                self.tables.append(table)
            if column not in self.columns:
                self.columns.append(column)

        # Update column types
        for table in fig.COLUMN_TYPES.keys():
            for column, col_type in fig.COLUMN_TYPES[table].items():
                self.col_types[column] = col_type
        self.tables = list(dict.fromkeys(self.tables))

    def check_column_types(self):
        """ Ensure each column will cast to its specified type """
        # Get the tables in the dataframe while maintaining order
        for (table, column) in self.df.axes[1]:

            # Get the specified types for additional metadata fields
            if table == 'AdditionalMetaData':
                # Add an error if the column name is one of the columns in the default template
                if column in self.col_types.keys():
                    err = '-1\t-1\tColumn Name Error: Column name {} is part of the default template'
                    self.errors.append(err.format(column))
                    continue
                # Otherwise attempt to get the type information
                else:
                    ctype = self.header_df[table][column].iloc[1]
                    if self.cur_col == 'HostSubjectId':
                        log('Host column type')
                        log(ctype)
                    # If no type is specified, add and error and default to str
                    if pd.isna(ctype) or ctype == '':
                        err = '-1\t-1\tAdditionalMetaData Column Error: Missing type information for column {}'
                        self.errors.append(err.format(column))
                        ctype = 'Text'
                    try:
                        self.col_types[column] = fig.TYPE_MAP[ctype]
                    except KeyError:
                        self.col_types[column] = fig.TYPE_MAP['Text']
                        err = '-1\t-1\tAdditionalMetaData Column Error: Invalid type information for column {}'
                        self.errors.append(err.format(column))
            # Make sure all values in the column will cast to the specified column type
            try:
                self.df[table].assign(column=self.df[table][column].astype(self.col_types[column]))
            # Additional metadata won't have an entry so will automatically be treated as a string
            except KeyError:
                self.df[table].assign(column=self.df[table][column].astype('object'))
            # Error handling for column values that don't match the column type
            except ValueError:
                err = '-1\t-1\tColumn Value Error: Column {} contains the wrong type of values'
                self.errors.append(err.format(column))

    def check_cell(self, row_index, cell, check_date=False):
        """
        Check the data in the specified cell.
        ====================================
        :row_index: The index of the row of the cell
        :col_index: The index of the column of the cell
        :cell: The value of the cell
        :col_type: The known type of the column as a whole
        :check_date: If True check the cell for a valid date
        """
        row_col = str(row_index) + '\t' + str(self.seen_cols.index(self.cur_col)) + '\t'

        # Check for consistent types in the column
        if not issubdtype(self.col_types[self.cur_col], datetime64):
            # If the cast fails for this cell the data must be the wrong type
            try:
                self.col_types[self.cur_col](cell)
            except ValueError:
                message = 'Mixed Type {}: Value {} does not match column type {}'
                if self.cur_table == 'AdditionalMetaData':
                    self.warnings.append(row_col + message.format('Warning', cell, self.col_types[self.cur_col]))
                else:
                    self.errors.append(row_col + message.format('Error', cell, self.col_types[self.cur_col]))

        # Check for empty fields
        if '' == cell:
            self.errors.append(row_col + 'Empty Cell Error: Empty cell value {}'.format(cell))

        # Checks if the cell is a string
        if isinstance(cell, str):
            # Check for trailing or preceding whitespace
            if not cell == cell.strip():
                self.errors.append(row_col + 'Whitespace Error: Preceding or trailing whitespace %s in row %d' %
                                   (cell, row_index))
            # Check for non-standard NAs
            if cell in NAs:
                self.errors.append(row_col + 'NA Error: Non standard NA format %s\t%d,%d' %
                                   (cell, row_index, self.seen_cols.index(self.cur_col)))
        # Check if this is the cell with the invalid date
        if check_date:
            try:
                pd.to_datetime(cell)
            except ValueError:
                self.errors.append(row_col + 'Date Error: Invalid date {} in row {}'.format(cell, row_index))

    def check_column(self, column, col_index):
        """
        Validate that there are no issues with the provided column of metadata.
        =======================================================================
        :col_index: The index of the column in the original dataframe
        """
        col_type = self.col_types[self.cur_col]

        # Get the header
        header = column.name

        # Check the header
        self.errors += check_header(header, col_index)

        # Check each cell in the column
        for i, cell in enumerate(column):
            if pd.isna(cell):
                # Check for missing required fields
                if self.header_df[self.cur_table][self.cur_col].iloc[0] == 'Required':
                    err = '{}\t{}\tMissing Required Value Error'
                    self.errors.append(err.format(i, self.seen_cols.index(self.cur_col)))
            else:
                self.check_cell(i, cell)

        # Ensure there is only one study being uploaded
        if header == 'StudyName' and len(set(column.tolist())) > 1:
            self.errors.append('-1\t-1\tMultiple Studies Error: Multiple studies in one metadata file')

        # Check that values fall within standard deviation
        if issubdtype(col_type, number):
            self.warnings += check_number_column(column, col_index, col_type)
        # Check for categorical data
        elif issubdtype(col_type, str) and not header == 'ICDCode':
            self.warnings += check_string_column(column, col_index)

    def check_dates(self, start, end):
        """
        Check that no dates in the end col are earlier than
        the matching date in the start col
        ===================================================
        :df: The data frame of the table containing the columns
        :table_col: The column of the offending start date
        """
        start_col = 0
        for i, row in self.df[self.cur_table].iterrows():
            if row[start] > row[end]:
                err = '{}\t{}\tData Range Error: End date {} is earlier than start date {} in row {}'
                self.errors.append(err.format(i + 1, start_col, row[start], row[end], i))

    def check_table_column(self):
        """ Check the columns of a particular table """
        col_index = self.columns.index(self.cur_col)
        if not self.cur_table == 'AdditionalMetaData' and self.cur_col not in fig.TABLE_COLS[self.cur_table]:
            if '.1' in self.cur_col:
                # Add an error if the column is a duplicate
                err_message = '-1\t{}\tDuplicate Column Error: Duplicate of column {} in table {}'
                self.errors.append(err_message.format(col_index, self.cur_col.replace('.1', ''), self.cur_table))
            else:
                # If the column shouldn't be in the table stop checking it
                err_message = '-1\t{}\tIllegal Column Error: Column {} should not be in table {}'
                self.errors.append(err_message.format(col_index, self.cur_col, self.cur_table))
                return
        col = self.table_df[self.cur_col]
        self.check_column(col, col_index)

        # Perform column specific checks
        if self.cur_table == 'Specimen':
            if self.cur_col == 'BarcodeSequence':
                self.errors += check_duplicates(col, col_index)
                self.errors += check_lengths(col, col_index)
                self.errors += check_barcode_chars(col, col_index)
            elif self.cur_col == 'RawDataID':
                self.errors += check_duplicates(col, col_index)
            elif self.cur_col == 'LinkerPrimerSequence':
                self.errors += check_lengths(col, col_index)
        elif self.cur_table == 'ICDCode':
            self.errors += check_ICD_codes(col, col_index)
        elif self.study_name is None and self.cur_table == 'Study':
            self.study_name.cur_table = self.table_df['StudyName'][0]

    def check_table(self):
        """
        Check the data within a particular table
        ========================================
        :table_df: A pandas dataframe containing the data for the specified table
        """
        start_col = None
        end_col = None
        self.table_df = self.df[self.cur_table]
        if not self.cur_table == 'AdditionalMetaData':
            missing_cols = set(fig.TABLE_COLS[self.cur_table]).difference(set(self.table_df.columns))
            if missing_cols:
                text = '-1\t-1\tMissing Column Error: Columns {} missing from table {}'
                self.errors.append(text.format(', '.join(missing_cols), self.cur_table))

        # For each table column
        for i, column in enumerate(self.table_df.columns):
            self.seen_cols.append(column)
            self.cur_col = column
            # Check that end dates are after start dates
            if re.match(r'\w*StartDate\w*', column):
                start_col = column
            elif re.match(r'\w*EndDate\w*', column):
                end_col = column
            self.check_table_column()

        # Compare the start and end dates
        if start_col is not None and end_col is not None:
            self.check_dates(start_col, end_col)

    def run(self):
        log('In validate_mapping_file')
        try:
            self.load_mapping_file(self.file_fp, self.sep)
            self.check_column_types()
            # For each table
            for table in self.tables:
                # If the table shouldn't exist add and error and skip checking it
                if table not in fig.TABLE_ORDER:
                    self.errors.append('-1\t-1\tIllegal Table Error: Table {} should not be the metadata'.format(table))
                else:
                    self.cur_table = table
                    self.seen_tables.append(table)
                    self.check_table()

            # Check for duplicate columns
            dups = check_duplicate_cols(self.seen_cols)
            if dups:
                for dup in dups:
                    locs = [i for i, header in enumerate(self.seen_cols) if header == 'dup']
                    for loc in locs:
                        self.errors.append('1\t{}\tDuplicate Header Error: Duplicate header {}'.format(loc, dup))

            # Check for missing tables
            missing_tables = fig.METADATA_TABLES.difference(set(self.tables))
            if missing_tables:
                self.errors.append('-1\t-1\tMissing Table Error: Missing tables ' + ', '.join(missing_tables))

            # Check for missing headers
            missing_columns = set(fig.COL_TO_TABLE.keys()).difference(set(self.seen_cols))
            if missing_columns:
                self.errors.append('-1\t-1\tMissing Column Error: Missing required fields: ' +
                                   ', '.join(missing_columns))
            try:
                self.subjects = self.df['Subjects']
            except KeyError:
                self.errors.append('Missing Table Error: Metadata must include the subjects table')
        except InvalidMetaDataFileError as e:
                self.errors.append(e.message)
        return self.errors, self.warnings, self.study_name, self.subjects
