#!/usr/bin/python

import pandas as pd
import mmeds.config as fig
from glob import glob
from random import randrange, getrandbits
from pathlib import Path


# Subjects Metadata Test Files
def write_test_metadata(df, output_path):
    """
    Write a dataframe or dictionary to a mmeds format metadata file.
    ================================================================
    :df: A pandas dataframe or python dictionary formatted like mmeds metadata
    :output_path: The path to write the metadata to
    """
    if isinstance(df, pd.DataFrame):
        mmeds_meta = df.to_dict('list')
    else:
        mmeds_meta = df

    # Create the header lines
    lines = ['\t'.join([key[0] for key in mmeds_meta.keys()]),
             '\t'.join([key[1] for key in mmeds_meta.keys()])]

    for row in range(len(df)):
        new_line = []
        for item in mmeds_meta.values():
            new_line.append(str(item[row]))
        lines.append('\t'.join(new_line))
    Path(output_path).write_text('\n'.join(lines) + '\n')


def write_error_files(df, file_type):
    if file_type == 'subject':
        random_col = ('Interventions', 'InterventionType')
        start_date_col = ('Illness', 'IllnessStartDate')
        end_date_col = ('Illness', 'IllnessEndDate')
        unique_col = ('Subjects', 'HostSubjectId')
        required_col = ('Subjects', 'HostSubjectId')
    elif file_type == 'specimen':
        random_col = ('Specimen', 'SpecimenInformation')
        start_date_col = ('Specimen', 'SpecimenCollectionDate')
        end_date_col = ('Specimen', 'SpecimenCollectionDate')
        unique_col = ('RawData', 'RawDataID')
        required_col = ('RawData', 'RawDataID')

    # Many Errors/Warnings
    many_error = df.copy(deep=True)
    for i in range(10):
        val = randrange(5, len(many_error))
        many_error.loc[val][end_date_col] = 'Not A Date'

    many_error = df.copy(deep=True)
    many_error.drop(random_col, axis=1, inplace=True)

    # Missing a table
    many_error = df.copy(deep=True)
    many_error.drop(unique_col[0], axis=1, inplace=True)

    write_test_metadata(many_error, '{}/{}_test_metadata_error.tsv'.format(file_path, file_type))

    # Parser issue
    issue_parsing = df.copy(deep=True)
    for i, val in enumerate(['\t', '\n', '\r']):
        issue_parsing.loc[5 + i][random_col] = val
    write_test_metadata(issue_parsing, '{}/{}_validate_error_issue_parsing.tsv'.format(file_path, file_type))
    # Mess up the file
    with open('{}/{}_validate_error_issue_parsing.tsv'.format(file_path, file_type), 'ab+') as f:
        f.write(bytearray(getrandbits(8) for _ in range(20)))

    # Wrong types
    wrong_type = df.copy(deep=True)
    for i in range(10):
        val = randrange(5, len(wrong_type))
        wrong_type.loc[val][start_date_col] = 'Not A Date'
    write_test_metadata(wrong_type, '{}/{}_validate_error_wrong_type.tsv'.format(file_path, file_type))

    # Illegal Column Header
    illegal_header = df.copy(deep=True)
    col = illegal_header[unique_col]
    col.rename(('AdditionalMetaData', 'IllegalColumn_'), inplace=True)
    illegal_header = illegal_header.join(col, how='outer')
    write_test_metadata(illegal_header, '{}/{}_validate_error_illegal_header.tsv'.format(file_path, file_type))

    # Illegal Column name
    column_name = df.copy(deep=True)
    col = column_name[unique_col]
    col.rename(('AdditionalMetaData', unique_col[1]), inplace=True)
    column_name = column_name.join(col, how='outer')
    write_test_metadata(column_name, '{}/{}_validate_error_column_name.tsv'.format(file_path, file_type))

    # Illegal Column
    illegal_column = df.copy(deep=True)
    col = illegal_column[required_col]
    col.rename((required_col[0], 'IllegalColumn'), inplace=True)
    illegal_column = illegal_column.join(col, how='outer')
    write_test_metadata(illegal_column, '{}/{}_validate_error_illegal_column.tsv'.format(file_path, file_type))

    # Illegal table
    illegal_table = df.copy(deep=True)
    col = illegal_table[random_col]
    col.rename(('IllegalTable', 'IllegalColumn'), inplace=True)
    illegal_table = illegal_table.join(col, how='outer')
    write_test_metadata(illegal_table, '{}/{}_validate_error_illegal_table.tsv'.format(file_path, file_type))

    # Missing a column
    missing_column = df.copy(deep=True)
    missing_column.drop(random_col, axis=1, inplace=True)
    write_test_metadata(missing_column, '{}/{}_validate_error_missing_column.tsv'.format(file_path, file_type))

    # Missing a table
    missing_table = df.copy(deep=True)
    missing_table.drop(random_col[0], axis=1, inplace=True)
    write_test_metadata(missing_table, '{}/{}_validate_error_missing_table.tsv'.format(file_path, file_type))

    # Empty Cells
    empty_cell = df.copy(deep=True)
    for i in range(10):
        val = randrange(3, len(empty_cell))
        empty_cell.loc[val][random_col] = ''
    write_test_metadata(empty_cell, '{}/{}_validate_error_empty_cell.tsv'.format(file_path, file_type))

    # Missing type
    missing_type = df.copy(deep=True)
    col = missing_type[random_col]
    col.rename(('AdditionalMetaData', 'NoTypeColumn'), inplace=True)
    for val in range(0, 3):
        col.loc[val] = ''
    missing_type = missing_type.join(col, how='outer')
    write_test_metadata(missing_type, '{}/{}_validate_error_missing_type.tsv'.format(file_path, file_type))

    # Invalid type
    invalid_type = df.copy(deep=True)
    col = invalid_type[random_col]
    col.rename(('AdditionalMetaData', 'NoTypeColumn'), inplace=True)
    for val in range(0, 3):
        col.loc[val] = 'NotAType'
    invalid_type = invalid_type.join(col, how='outer')
    write_test_metadata(invalid_type, '{}/{}_validate_error_invalid_type.tsv'.format(file_path, file_type))

    # Whitespace
    whitespace = df.copy(deep=True)
    whitespace.iloc[10][random_col] = \
        ' ' + whitespace.iloc[10][random_col] + ' '
    write_test_metadata(whitespace, '{}/{}_validate_error_whitespace.tsv'.format(file_path, file_type))

    # Missing Required Value
    missing_required_value = df.copy(deep=True)
    for i in range(10):
        val = randrange(3, len(missing_required_value))
        missing_required_value.loc[val][required_col] = 'NA'
    write_test_metadata(missing_required_value,
                        '{}/{}_validate_error_missing_required_value.tsv'.format(file_path, file_type))

    # Non Standard NA
    non_standard_na = df.copy(deep=True)
    for i in range(10):
        val = randrange(3, len(non_standard_na))
        non_standard_na.loc[val][random_col] = 'n.a.'
    write_test_metadata(non_standard_na, '{}/{}_validate_error_non_standard_na.tsv'.format(file_path, file_type))

    # Numeric Header Column
    number_header = df.copy(deep=True)
    col = number_header[random_col]
    col.rename(('AdditionalMetaData', '0'), inplace=True)
    number_header = number_header.join(col, how='outer')
    write_test_metadata(number_header, '{}/{}_validate_error_number_header.tsv'.format(file_path, file_type))

    # na Header Column
    na_header = df.copy(deep=True)
    col = na_header[random_col]
    col.rename(('AdditionalMetaData', 'na'), inplace=True)
    na_header = na_header.join(col, how='outer')
    write_test_metadata(na_header, '{}/{}_validate_error_na_header.tsv'.format(file_path, file_type))

    # duplicate Column
    duplicate_column = df.copy(deep=True)
    col = duplicate_column[random_col]
    col.rename(('AdditionalMetaData', 'DupColumn'), inplace=True)
    duplicate_column = duplicate_column.join(col, how='outer')
    col.rename(('AdditionalMetaData', 'DupColumn.1'), inplace=True)
    duplicate_column = duplicate_column.join(col, how='outer')
    write_test_metadata(duplicate_column, '{}/{}_validate_error_duplicate_column.tsv'.format(file_path, file_type))

    # duplicate value
    duplicate_value = df.copy(deep=True)
    duplicate_value.iloc[10][unique_col] = duplicate_value.iloc[11][unique_col]
    write_test_metadata(duplicate_value, '{}/{}_validate_error_duplicate_value.tsv'.format(file_path, file_type))

    # future_date
    future_date = df.copy(deep=True)
    future_date.iloc[10][start_date_col] = '2222-2-1'
    write_test_metadata(future_date, '{}/{}_validate_error_future_date.tsv'.format(file_path, file_type))

    # Length error
    cell_length = df.copy(deep=True)
    cell_length.iloc[10][random_col] = 'asdfasdf' * 40
    write_test_metadata(cell_length, '{}/{}_validate_error_cell_length.tsv'.format(file_path, file_type))

    if file_type == 'subject':
        # invalid_icd_code
        invalid_icd_code = df.copy(deep=True)
        invalid_icd_code.iloc[10]['ICDCode']['ICDCode'] = 'NotACode'
        write_test_metadata(invalid_icd_code, '{}/{}_validate_error_invalid_icd_code.tsv'.format(file_path, file_type))

        # phi Header Column
        phi_header = df.copy(deep=True)
        col = phi_header[('Subjects', 'HostSubjectId')]
        col.rename(('AdditionalMetaData', 'Address'), inplace=True)
        phi_header = phi_header.join(col, how='outer')
        write_test_metadata(phi_header, '{}/{}_validate_error_phi_header.tsv'.format(file_path, file_type))

        # invalid_date range
        invalid_date_range = df.copy(deep=True)
        invalid_date_range.iloc[10][start_date_col] = '2012-05-1'
        invalid_date_range.iloc[10][end_date_col] = '2011-05-1'
        write_test_metadata(invalid_date_range,
                            '{}/{}_validate_error_invalid_date_range.tsv'.format(file_path, file_type))

    elif file_type == 'specimen':
        # different_length
        different_length = df.copy(deep=True)
        different_length.iloc[10]['RawData']['BarcodeSequence'] =\
            different_length.iloc[10]['RawData']['BarcodeSequence'][:5]
        write_test_metadata(different_length, '{}/{}_validate_error_different_length.tsv'.format(file_path, file_type))

        # invalid_barcodesequence
        invalid_barcodesequence = df.copy(deep=True)
        invalid_barcodesequence.iloc[10]['RawData']['BarcodeSequence'] =\
            invalid_barcodesequence.iloc[10]['RawData']['BarcodeSequence'][:-1] + 'J'
        write_test_metadata(invalid_barcodesequence,
                            '{}/{}_validate_error_invalid_barcodesequence.tsv'.format(file_path, file_type))

        # Multiple Studies in a single metadata file
        multiple_studies = df.copy(deep=True)
        if i in range(5, 10):
            multiple_studies.iloc[10]['Study']['StudyName'] = 'OtherStudy'
        write_test_metadata(multiple_studies, '{}/{}_validate_error_multiple_studies.tsv'.format(file_path, file_type))


def write_warning_files(df, file_type):
    # Multiple Warnings
    if file_type == 'subject':
        random_col = ('Interventions', 'InterventionType')
        cat_col = ('Subjects', 'Nationality')
        std_col = ('Weights', 'Weight')
    elif file_type == 'specimen':
        random_col = ('Specimen', 'SpecimenInformation')
        cat_col = ('ResultsProtocols', 'ResultsMethod')
        std_col = ('Specimen', 'SpecimenWeight')

    test_warning = df.copy(deep=True)
    test_warning.iloc[10][random_col] = '9'
    test_warning.iloc[10][cat_col] = 'Protocol90'
    write_test_metadata(test_warning, '{}/{}_test_metadata_warn.tsv'.format(file_path, file_type))

    # stddev_warning
    stddev_warning = df.copy(deep=True)
    stddev_warning.iloc[10][std_col] = '9'
    write_test_metadata(stddev_warning, '{}/{}_validate_warning_stddev_warning.tsv'.format(file_path, file_type))

    # categorical_data
    categorical_data = df.copy(deep=True)
    categorical_data.iloc[10][cat_col] = 'Protocol90'
    write_test_metadata(categorical_data, '{}/{}_validate_warning_categorical_data.tsv'.format(file_path, file_type))


def write_alternate_files(df, file_type):
    if file_type == 'subject':
        col_one = ('Subjects', 'Nationality')
        col_two = ('Illness', 'IllnessDescription')
    elif file_type == 'specimen':
        col_one = ('RawData', 'RawDataDescription')
        col_two = ('Aliquot', 'AliquotID')

    test_alt = df.copy(deep=True)
    for val in range(len(test_alt)):
        test_alt.loc[val][col_one] = test_alt.loc[val][col_one] + '_alt'
        test_alt.loc[val][col_two] = test_alt.loc[val][col_two] + '_alt'
    write_test_metadata(test_alt, '{}/{}_test_metadata_alt.tsv'.format(file_path, file_type))


# Specimen Metadata Test Files


if __name__ == '__main__':

    file_path = '/home/david/Work/mmeds-meta/mmeds/test_files/validation_files/'
    for test_file in glob(file_path + 'validate_*'):
        print('Deleting {}'.format(test_file))
        Path(test_file).unlink()

    # Create the subjects test files
    df = pd.read_csv(fig.TEST_SUBJECT, sep='\t', header=[0, 1], na_filter=False)
    write_error_files(df, 'subject')
    write_warning_files(df, 'subject')
    write_alternate_files(df, 'subject')

    # Create the specimen test files
    df = pd.read_csv(fig.TEST_SPECIMEN, sep='\t', header=[0, 1], na_filter=False)
    write_error_files(df, 'specimen')
    write_warning_files(df, 'specimen')
    write_alternate_files(df, 'specimen')
