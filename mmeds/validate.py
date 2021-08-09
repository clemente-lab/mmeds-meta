import pandas as pd
import mmeds.config as fig
import re

from collections import defaultdict
from numpy import std, mean, datetime64
from mmeds.util import load_ICD_codes, is_numeric, load_metadata
from mmeds.error import InvalidMetaDataFileError
from datetime import datetime

from mmeds.logging import Logger


NAs = ['n/a', 'n.a.', 'n_a', 'na', 'N/A', 'N.A.', 'N_A']

HIPAA_HEADERS = ['social_security', 'social_security_number', 'address', 'phone', 'phone_number']

DNA = set('GATC')

ILLEGAL_IN_HEADER = set('/\\ *?_.,')  # Limit to alpha numeric, hyphen, has to start with alpha
ILLEGAL_IN_CELL = set(str(ILLEGAL_IN_HEADER))


def validate_mapping_file(file_fp, study_name, metadata_type, subject_ids, subject_type, delimiter='\t'):
    """
    Checks the mapping file at file_fp for any errors.
    Returns a list of the errors and warnings,
    an empty list means there were no issues.
    """
    valid = Validator(file_fp, study_name, metadata_type, subject_ids, subject_type, sep=delimiter)
    return valid.run()


def valid_additional_file(file_fp, data_table, generate=True):
    """
    Checks that the provided file is valid for the specified ID type
    ================================================================
    :file_fp: A string, Path to the file to check
    :data_table: A string, The table this data relates to
    :generate: A boolean, if True then this file will be used for ID generation.
        If False the IDs already exist in the file being uploaded
    """
    valid = True
    if data_table == 'aliquot':
        cols = fig.ALIQUOT_ID_COLUMNS
    elif data_table == 'sample':
        cols = fig.SAMPLE_ID_COLUMNS
    elif data_table == 'subject':
        cols = fig.SUBJECT_COLUMNS
    else:
        raise InvalidMetaDataFileError(f"The provided file type ({data_table}) is not valid")

    Logger.error(f'Generate: {generate}')
    # IF the ID is not being generated add it to the dict
    if not generate:
        cols[f'{data_table.capitalize()}ID'] = str

    Logger.error(cols.values())

    try:  # Check the file can actually be parsed
        df = pd.read_csv(file_fp, sep='\t')
    except pd.errors.ParserError as e:
        valid = False
        Logger.error("Invalid file type")
        Logger.error(e)
    else:
        file_cols = df.columns.tolist()
        if 'StudyName' not in file_cols:
            valid = False
        else:
            file_cols.remove('StudyName')
        diff = set(file_cols).difference(cols)
        # Check that all the correct columns and only the correct columns are included
        if diff:
            Logger.error(f"Invalid columns in ID file as {file_fp}")
            Logger.error(diff)
            valid = False
        else:
            valid = cast_columns(df, cols, file_cols) and valid
    return valid


def cast_columns(df, cols, file_cols):
    """ Casts columns in df to specified types """
    result = True
    for column in file_cols:
        try:  # Date objects need a special cast
            if cols[column] == pd.Timestamp:
                df[column] = pd.to_datetime(df[column])
            else:
                df[column].astype(cols[column])
        except ValueError:
            Logger.error("Invalid types in ID file")
            result = False
            break
    return result


class Validator:

    def __init__(self, file_fp, study_name, metadata_type, subject_ids, subject_type, sep='\t'):
        """ Initialize the validator object. """
        self.study_name = study_name
        self.metadata_type = metadata_type
        self.subject_type = subject_type
        self.errors = []
        self.warnings = []
        self.subjects = []
        self.file_fp = file_fp
        self.sep = sep
        self.header_df = None
        self.df = None
        self.tables = []
        self.columns = []

        self.col_types = {}
        self.table_df = None
        self.reference_header = None
        self.cur_col = None    # Current column being checked
        self.cur_row = 0       # Current row being checked
        self.cur_table = None  # Current table being checked

        self.seen_tables = []
        self.seen_cols = []
        self.col_index = 0

        # List of ids found in subject metadata
        # used when validating specimen metadata
        self.subject_ids = subject_ids

    def check_number_column(self, column):
        """ Check for mixed types and values outside two standard deviations. """
        Logger.debug("check number column")
        filtered = [self.col_type(x) for x in column.tolist() if is_numeric(x)]
        Logger.debug("Filtered")
        Logger.debug(filtered)
        stddev = std(filtered)
        avg = mean(filtered)
        for i, cell in enumerate(filtered):
            Logger.debug(f"{i}: {cell}")
            if (cell > avg + (2 * stddev) or cell < avg - (2 * stddev)):
                Logger.debug("Outside stddev")
                text = '{}\t{}\tStdDev Warning: Value {} outside of two standard deviations of mean in column {}'
                self.warnings.append(text.format(i, self.col_index, cell, self.col_index))
        Logger.debug("Finished check number column")

    def check_string_column(self, column):
        """ Check for categorical data. """
        Logger.debug("In check string column")
        counts = column.value_counts()
        stddev = std(counts.values)
        avg = mean(counts.values)
        Logger.debug('Got counts')
        for val, count in counts.iteritems():
            Logger.debug(f'{val}: {count}')
            if count < (avg - stddev) and count < 3:
                Logger.debug("Potential categorical data")
                text = ('{}\t{}\tCategorical Data Warning: Potential categorical data detected.' +
                        ' Value {} may be in error, only {} found.')
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
        err_str = '{}\t{}\tDuplicate Value Error: Duplicate value {} of row {} in row {} in column {}.'
        for dup_key in dups.keys():
            value = dups[dup_key]
            for val in value[1:]:
                self.errors.append(err_str.format(val, self.col_index, dup_key, value[0], val, self.cur_col))

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

        Logger.debug("iterate over cells")
        if column.isna().all():
            if (not self.cur_table == 'AdditionalMetaData' and
                self.reference_header[self.cur_table][self.cur_col].iloc[0] == 'Required'):

                Logger.debug("Column shouldn't be NA")
                err = '{}\t{}\tMissing Required Value Error'
                self.errors.append(err.format(-1, self.seen_cols.index(self.cur_col)))
        else:
            # Check each cell in the column
            for i, cell in enumerate(column):
                if pd.isna(cell):
                    Logger.debug("Cell is NA")
                    # Check for missing required fields
                    if self.reference_header[self.cur_table][self.cur_col].iloc[0] == 'Required':
                        Logger.debug("Cell shouldn't be NA")
                        err = '{}\t{}\tMissing Required Value Error'
                        self.errors.append(err.format(i, self.seen_cols.index(self.cur_col)))
                else:
                    self.check_cell(i, cell)

            # Ensure there is only one study being uploaded
            if header == 'StudyName' and len(set(column.tolist())) > 1:
                self.errors.append('-1\t-1\tMultiple Studies Error: Multiple studies in one metadata file')

            Logger.debug("Checked StudyName")

            # Check that values fall within standard deviation
            if self.col_type == int or self.col_type == float:
                Logger.debug("check number column")
                self.check_number_column(column)
            # Check for categorical data
            elif self.col_type == str and not header == 'ICDCode':
                Logger.debug("Check string column")
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
                self.errors.append(err.format(i, start_col, row[end], row[start], i))

    def check_table_column(self):
        """ Check the columns of a particular table """
        Logger.debug("In check table column")
        self.col_index = self.columns.index(self.cur_col)
        if not self.cur_table == 'AdditionalMetaData' and self.cur_col not in fig.TABLE_COLS[self.cur_table]:
            Logger.debug("If not additional metadata and col not in table")
            # If the column shouldn't be in the table stop checking it
            err_message = '-1\t{}\tIllegal Column Error: Column {} should not be in table {}'
            self.errors.append(err_message.format(self.col_index, self.cur_col, self.cur_table))
        else:
            Logger.debug("If additional metadata")
            # Check the header
            self.check_header()

            col = self.table_df[self.cur_col]
            Logger.debug("run check_column")
            # Check the column itself
            self.check_column(col)
            Logger.debug("ran check_columns")
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
                self.check_NA(col)
            elif self.cur_col == 'IllnessInstanceID':
                self.check_duplicates(col)
            Logger.debug("finished check_table_column")

    def check_table(self):
        """
        Check the data within a particular table
        ========================================
        :table_df: A pandas dataframe containing the data for the specified table
        """
        start_col = None
        end_col = None
        Logger.debug(f"Checking table {self.cur_table}")
        # Get the table from the metadata being validated
        try:
            self.table_df = self.df[self.cur_table]
            Logger.debug("got table df")
        # If it doesn't exist in the metadata
        except KeyError:
            Logger.debug("Table not in metadata")
            # if isn't not a special case table add the appropriate error
            if self.cur_table not in ({'AdditionalMetaData'} | fig.ICD_TABLES):
                self.errors.append('-1\t-1\tMissing Table Error: Missing table {}'.format(self.cur_table))
            Logger.debug("Added error")
        # If it does exist continue validation
        else:
            # For the built in table, ensure all columns are present
            if not self.cur_table == 'AdditionalMetaData':
                Logger.debug("Not additional metadata")
                missing_cols = set(fig.TABLE_COLS[self.cur_table]).difference(set(self.table_df.columns))
                if missing_cols:
                    Logger.debug(f"Missing columns {missing_cols}")
                    text = '-1\t-1\tMissing Column Error: Columns {} missing from table {}'
                    self.errors.append(text.format(', '.join(missing_cols), self.cur_table))
            # Check that subjects match
            elif self.metadata_type == 'specimen':
                self.check_matching_subjects()

            Logger.debug("Iterate over columns")
            for i, column in enumerate(self.table_df.columns):
                Logger.debug(f"Check column {column}")
                # Track what column is being validated
                self.seen_cols.append(column)
                self.cur_col = column

                # Check that end dates are after start dates
                if re.match(r'\w*StartDate\w*', column):
                    start_col = column
                elif re.match(r'\w*EndDate\w*', column):
                    end_col = column
                Logger.debug("regex matched dates")
                self.check_table_column()

            # Compare the start and end dates
            if start_col is not None and end_col is not None and\
                    pd.api.types.is_datetime64_ns_dtype(self.df[(self.cur_table, start_col)]) and\
                    pd.api.types.is_datetime64_ns_dtype(self.df[(self.cur_table, end_col)]):
                self.check_dates(start_col, end_col)
            Logger.debug("checked dates")

            # Get the study name from that table
            if self.cur_table == 'Study':
                self.study_name = self.table_df['StudyName'][0]
            Logger.debug("Got study name")

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
        try:
            self.df = load_metadata(self.file_fp)
            self.header_df = pd.read_csv(self.file_fp,
                                         sep=self.sep,
                                         header=[0, 1],
                                         nrows=3)
            if self.metadata_type == 'subject':
                if self.subject_type == 'human':
                    self.reference_header = pd.read_csv(fig.TEST_SUBJECT,
                                                        sep=self.sep,
                                                        header=[0, 1],
                                                        nrows=3)
                elif self.subject_type == 'animal':
                    self.reference_header = pd.read_csv(fig.TEST_ANIMAL_SUBJECT,
                                                        sep=self.sep,
                                                        header=[0, 1],
                                                        nrows=3)
            elif self.metadata_type == 'specimen':
                self.reference_header = pd.read_csv(fig.TEST_SPECIMEN,
                                                    sep=self.sep,
                                                    header=[0, 1],
                                                    nrows=3)
        except (pd.errors.ParserError, UnicodeDecodeError):
            raise InvalidMetaDataFileError('-1\t-1\tThere is an issue parsing your metadata. Please check that it is' +
                                           ' in tab delimited format with no tab or newline characters in any of the' +
                                           ' cells')

    def setup_tables_columns(self):
        # Setup the tables and columns
        for table, column in self.df.columns:
            if table not in self.tables:
                self.tables.append(table)
            if column not in self.columns:
                self.columns.append(column)

        if self.metadata_type == 'subject':
            if self.subject_type == 'human':
                col_types = fig.COLUMN_TYPES_SUBJECT
            elif self.subject_type == 'animal':
                col_types = fig.COLUMN_TYPES_ANIMAL_SUBJECT
        else:
            col_types = fig.COLUMN_TYPES_SPECIMEN

        # Update column types
        for table in col_types.keys():
            for column, col_type in col_types[table].items():
                self.col_types[column] = col_type
        self.tables = list(dict.fromkeys(self.tables))

    def check_column_types(self):
        """ Ensure each column will cast to its specified type """
        # Get the tables in the dataframe while maintaining order
        for (table, column) in self.df.axes[1]:
            # Get the specified types for additional metadata fields
            if table == 'AdditionalMetaData':
                # Add an error if the column name is one of the columns in the default template
                if column in fig.ALL_COLS:
                    err = '-1\t-1\tColumn Name Error: Column name {} is part of the default template'
                    self.errors.append(err.format(column))

            # Check the type information is valid
            ctype = self.header_df[table][column].iloc[1]
            try:
                self.col_types[column] = fig.TYPE_MAP[ctype]
            except KeyError:
                # If no type is specified, add and error and default to str
                if pd.isna(ctype) or ctype == '':
                    err = '-1\t{}\tColumn Missing Type Error: Missing type information for column {}'
                    self.errors.append(err.format(self.col_index, column))
                else:
                    err = '-1\t{}\tColumn Invalid Type Error: Invalid type information for column {}'
                    self.errors.append(err.format(self.col_index, column))
                self.col_types[column] = fig.TYPE_MAP['Text']

            if self.col_types[column] == pd.Timestamp:
                try:
                    cast_column = pd.to_datetime(self.df[(table, column)])
                    self.df[(table, column)] = cast_column
                except ValueError:
                    err = '-1\t{}\tColumn Wrong Type Error: Column {} contains the wrong type of values'
            else:
                self.df[table][column].astype(self.col_types[column])

    def check_matching_subjects(self):
        """ Insure the subjects match those previouvs found in subject metadata """
        # Get the subjects identified in the specimen metadata
        specimen_subs = self.df['AdditionalMetaData']['SubjectIdCol'].tolist()
        if self.subject_type == 'human':
            check_subs = self.subject_ids['HostSubjectId']
        elif self.subject_type == 'animal':
            check_subs = self.subject_ids['AnimalSubjectID']
        diff = set(check_subs).symmetric_difference(set(specimen_subs))
        err = '{}\t{}\tMissing Subject Error: Subject with ID {} found in {} metadata file but not {} metadata'
        for sub in diff:
            try:
                row_index = specimen_subs.index(sub)
                found = 'specimen'
                other = 'subject'
            except ValueError:
                row_index = self.subject_ids['HostSubjectId'].tolist().index(sub)
                found = 'subject'
                other = 'specimen'
            self.errors.append(err.format(row_index, self.col_index, sub, found, other))

    def check_study_name(self):
        """ Check that the study name input by the user matches that in the metadata """
        df_study_name = self.df['Study']['StudyName'][0]
        if not self.study_name == df_study_name:
            self.errors.append(f'-1\t-1\tStudy Name Error: The study name in the metadata ({df_study_name})' +
                               f' does not match the name provided for this upload ({self.study_name})')

    def run(self):
        """ Perform the validation. """
        Logger.debug("Running metadata validation")
        subjects = pd.DataFrame()
        # Try loading the metadata to be validated
        try:
            self.load_mapping_file(self.file_fp, self.sep)
            Logger.debug("loaded_mapping_file")
            self.setup_tables_columns()
            Logger.debug("Setup tables columns")
        # If loading fails the file is invalid and no more checks can be performed
        except InvalidMetaDataFileError as e:
            self.errors.append(e.message)
        # Otherwise proceed with validation
        else:
            if self.metadata_type == 'subject':
                Logger.debug("metadata type subject")
                if self.subject_type == 'human':
                    Logger.debug("Subject Type Human")
                    tables = fig.SUBJECT_TABLES
                    if 'Subjects' in self.df.keys():
                        # Only define subjects if subject table is correctly uploaded
                        subjects = self.df['Subjects']
                    Logger.debug("Subjects defined")
                elif self.subject_type == 'animal':
                    tables = fig.ANIMAL_SUBJECT_TABLES
                    if 'AnimalSubjects' in self.df.keys():
                        # Only define subjects if subject table is correctly uploaded
                        subjects = self.df['AnimalSubjects']
            elif self.metadata_type == 'specimen':
                self.check_study_name()
                tables = fig.SPECIMEN_TABLES
            Logger.debug("Checking COlumn Types")
            self.check_column_types()
            Logger.debug("Checked column types")

            # Check for missing tables
            missing_tables = tables.difference(set(self.tables)) - ({'AdditionalMetaData'} | fig.ICD_TABLES)
            Logger.debug("Checked missing tables")
            if missing_tables:
                self.errors.append('-1\t-1\tMissing Table Error: Missing tables ' + ', '.join(missing_tables))
            Logger.debug("Going through tables")
            # For each table
            for table in self.tables:
                # If the table shouldn't exist add and error and skip checking it
                if table in tables:
                    self.cur_table = table
                    self.seen_tables.append(table)
                    self.check_table()
                else:
                    self.errors.append('-1\t-1\tIllegal Table Error: Table {} should not be the metadata'.format(table))
            Logger.debug("Done")

        return self.errors, self.warnings, subjects
