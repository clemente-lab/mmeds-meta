import pandas as pd
import mmeds.config as fig
import re

from collections import defaultdict
from numpy import std, mean
from mmeds.util import log, load_ICD_codes, is_numeric, load_metadata
from mmeds.error import InvalidMetaDataFileError
from datetime import datetime


NAs = ['n/a', 'n.a.', 'n_a', 'na', 'N/A', 'N.A.', 'N_A']

HIPAA_HEADERS = ['social_security', 'social_security_number', 'address', 'phone', 'phone_number']

DNA = set('GATC')

ILLEGAL_IN_HEADER = set('/\\ *?_.,')  # Limit to alpha numeric, hyphen, has to start with alpha
ILLEGAL_IN_CELL = set(str(ILLEGAL_IN_HEADER))


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
        self.col_index = 0

    def check_number_column(self, column):
        """ Check for mixed types and values outside two standard deviations. """
        filtered = [self.col_type(x) for x in column.tolist() if is_numeric(x)]
        stddev = std(filtered)
        avg = mean(filtered)
        for i, cell in enumerate(filtered):
            if (cell > avg + (2 * stddev) or cell < avg - (2 * stddev)):
                text = '{}\t{}\tStdDev Warning: Value {} outside of two standard deviations of mean in column {}'
                self.warnings.append(text.format(i, self.col_index, cell, self.col_index))

    def check_string_column(self, column):
        """ Check for categorical data. """
        counts = column.value_counts()
        stddev = std(counts.values)
        avg = mean(counts.values)
        for val, count in counts.iteritems():
            if count < (avg - stddev) and count < 3:
                text = '{}\t{}\tCategorical Data Warning: Potential categorical data detected.' +\
                    ' Value {} may be in error, only {} found.'
                self.warnings.append(text.format(-1, self.col_index, val, count))

    def check_lengths(self, column):
        """ Checks that all entries have the same length in the provided column """
        length = len(column[0])
        for i, cell in enumerate(column[1:]):
            if not len(cell) == length:
                err = '{}\t{}\tLength Error: Value {} has a different length from other values in column {}'
                self.errors.append(err.format(i, self.col_index, cell, self.col_index))

    def check_barcode_chars(self, column):
        """ Check that BarcodeSequence only contains valid DNA characters. """
        for i, cell in enumerate(column):
            diff = set(cell).difference(DNA)
            if diff:
                self.errors.append('%d\t%d\tBarcode Error: Invalid BarcodeSequence char(s) %s in row %d' %
                                   (i, self.col_index, ', '.join(diff), i))

    def check_ICD_codes(self, column):
        """ Ensures all ICD codes in the column are valid. """
        # Load the ICD codes
        ICD_codes = load_ICD_codes()
        for i, cell in enumerate(column):
            if not pd.isnull(cell):
                parts = cell.split('.')
                if (ICD_codes.get(parts[0]) is None or ICD_codes.get(parts[0]).get(parts[1]) is None):
                    err = '{}\t{}\tICD Code Error: Invalid ICD code {} in row {}'
                    self.errors.append(err.format(i, self.col_index, cell, i))

    def check_NA(self, column):
        """ Checks for any NA values in the provided column """
        err = '{row}\t{col}\tNA Value Error: No NAs allowed in column {col}'
        for i, value in enumerate(column):
            if value == 'NA':
                self.errors.append(err.format(row=i, col=self.col_index))

    def check_duplicates(self, column):
        """ Checks for any duplicate entries in the provided column """
        cells = defaultdict(list)

        # Add the indices of each item
        for i, cell in enumerate(column):
            cells[cell].append(i)
        # Find any duplicates
        dups = {k: v for k, v in cells.items() if len(v) > 1}
        for dup_key in dups.keys():
            value = dups[dup_key]
            for val in value[1:]:
                self.errors.append('%d\t%d\tDuplicate Value Error: Duplicate value of row %d, %s in row %d.' %
                                   (val, self.col_index, value[0], dup_key, val))

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
        try:
            # Try casting the cell to its type
            cast_cell = self.col_type(cell)

            # Checks if the cell is a string
            if self.col_type == str:
                # Check for empty fields
                if '' == cell:
                    self.errors.append(row_col + 'Empty Cell Error: Empty cell value {}'.format(cell))
                # Check for non-standard NAs
                elif cast_cell in NAs:
                    self.errors.append(row_col + 'NA Error: Non standard NA format {}'.format(cast_cell))
                # Check for trailing or preceding whitespace
                elif not cast_cell == cast_cell.strip():
                    err = 'Whitespace Error: Preceding or trailing whitespace {}'
                    self.errors.append(row_col + err.format(cast_cell))
                # Check the cell isn't too long
                if not self.cur_table == 'AdditionalMetaData' and len(cast_cell) > fig.COL_SIZES[self.cur_col][1]:
                    err = 'Cell Length Error: Cell value {} is too long for the column'
                    self.errors.append(row_col + err.format(cast_cell))
            # Check if this is the cell with the invalid date
            elif self.col_type == pd.Timestamp:
                if cast_cell.date() > datetime.now().date():
                    self.errors.append(row_col + 'Future Date Error: Date {} has not yet occurred'.format(cell))
        # Error handling for column values that don't match the column type
        except ValueError:
            err = 'Cell Wrong Type Error: Cell {} contains the wrong type of values'
            self.errors.append(row_col + err.format(cell))

    def check_column(self, column):
        """
        Validate that there are no issues with the provided column of metadata.
        =======================================================================
        :col_index: The index of the column in the original dataframe
        """
        self.col_type = self.col_types[self.cur_col]

        # Get the header
        header = column.name

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
        if self.col_type == int or self.col_type == float:
            self.check_number_column(column)
        # Check for categorical data
        elif self.col_type == str and not header == 'ICDCode':
            self.check_string_column(column)

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
                err = '{}\t{}\tInvalid Date Range Error: End date {} is earlier than start date {} in row {}'
                self.errors.append(err.format(i, start_col, row[start], row[end], i))

    def check_table_column(self):
        """ Check the columns of a particular table """

        self.col_index = self.columns.index(self.cur_col)
        if not self.cur_table == 'AdditionalMetaData' and self.cur_col not in fig.TABLE_COLS[self.cur_table]:
            # If the column shouldn't be in the table stop checking it
            err_message = '-1\t{}\tIllegal Column Error: Column {} should not be in table {}'
            self.errors.append(err_message.format(self.col_index, self.cur_col, self.cur_table))
            return

        # Check the header
        self.check_header()

        col = self.table_df[self.cur_col]
        # Check the column itself
        self.check_column(col)

        # Perform column specific checks
        if self.cur_table == 'RawData':
            if self.cur_col == 'BarcodeSequence':
                self.check_duplicates(col)
                self.check_lengths(col)
                self.check_barcode_chars(col)
                self.check_NA(col)
            elif self.cur_col == 'RawDataID':
                self.check_duplicates(col)
                self.check_NA(col)
            elif self.cur_col == 'LinkerPrimerSequence':
                self.check_lengths(col)
        elif self.cur_table == 'ICDCode':
            self.check_ICD_codes(col)
        elif self.cur_col == 'HostSubjectId':
            self.check_duplicates(col)
            self.check_NA(col)

    def check_table(self):
        """
        Check the data within a particular table
        ========================================
        :table_df: A pandas dataframe containing the data for the specified table
        """
        start_col = None
        end_col = None
        self.table_df = self.df[self.cur_table]
        # For the built in table, ensure all columns are present
        if not self.cur_table == 'AdditionalMetaData':
            missing_cols = set(fig.TABLE_COLS[self.cur_table]).difference(set(self.table_df.columns))
            if missing_cols:
                text = '-1\t-1\tMissing Column Error: Columns {} missing from table {}'
                self.errors.append(text.format(', '.join(missing_cols), self.cur_table))

        # For each table column
        for i, column in enumerate(self.table_df.columns):
            # Track what column is being validated
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
        # Get the study name from that table
        if self.cur_table == 'Study':
            self.study_name = self.table_df['StudyName'][0]

    def check_header(self):
        """ Check the header field to ensure it complies with MMEDS requirements. """
        row_col = '1\t{}\t'.format(self.col_index)

        # Check if it's numeric
        if is_numeric(self.cur_col):
            text = 'Number Header Error: Column names cannot be numbers. Replace header {}'
            self.errors.append(row_col + text.format(self.cur_col))
        # Check if it's NA
        if self.cur_col in NAs + ['NA']:
            err = 'NA Header Error: Column names cannot be NA. Replace  self.cur_col {} of column {}'
            self.errors.append(row_col + err.format(self.cur_col, self.col_index))
        # Check for illegal characters
        if ILLEGAL_IN_HEADER.intersection(set(self.cur_col)):
            # This will catch duplicate columns which will show up in the dataframe like
            # ColA, ColA.1, ColA.2, etc
            try:
                # See if the part after the '.' is a number
                int(self.cur_col.split('.')[1])
                err = 'Duplicate Column Error: Column {} is possibly a duplicate of another column.' +\
                    'If this is not the case remove the "." from the self.cur_col of column {}'
                self.errors.append(row_col + err.format(self.cur_col, self.col_index))
            except (ValueError, IndexError):
                illegal_chars = ILLEGAL_IN_HEADER.intersection(set(self.cur_col))
                err = 'Illegal Header Error: Illegal character(s) {}. Replace self.cur_col {} of column {}'
                illegal = '({})'.format(','.join(illegal_chars).replace(' ', '<space>').replace('\t', '<tab>'))
                self.errors.append(row_col + err.format(illegal, self.cur_col, self.col_index))
        # Check for HIPAA non-compliant self.cur_cols
        if self.cur_col.lower() in HIPAA_HEADERS:
            err = 'PHI Header Error: Potentially identifying information in {}'
            self.errors.append(row_col + err.format(self.cur_col))

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
        except (pd.errors.ParserError, UnicodeDecodeError):
            raise InvalidMetaDataFileError('-1\t-1\tThere is an issue parsing your metadata. Please check that it is' +
                                           ' in tab delimited format with no tab or newline characters in any of the' +
                                           ' cells')
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
                    # If no type is specified, add and error and default to str
                    if pd.isna(ctype) or ctype == '':
                        err = '-1\t{}\tColumn Missing Type Error: Missing type information for column {}'
                        self.errors.append(err.format(self.col_index, column))
                        ctype = 'Text'
                    try:
                        self.col_types[column] = fig.TYPE_MAP[ctype]
                    except KeyError:
                        self.col_types[column] = fig.TYPE_MAP['Text']
                        err = '-1\t{}\tColumn Invalid Type Error: Invalid type information for column {}'
                        self.errors.append(err.format(self.col_index, column))

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

            # Check for missing tables
            missing_tables = fig.METADATA_TABLES.difference(set(self.tables))
            if missing_tables:
                self.errors.append('-1\t-1\tMissing Table Error: Missing tables ' + ', '.join(missing_tables))

            try:
                self.subjects = self.df['Subjects']
            except KeyError:
                self.errors.append('Missing Table Error: Metadata must include the subjects table')
        except InvalidMetaDataFileError as e:
                self.errors.append(e.message)
        return self.errors, self.warnings, self.subjects
