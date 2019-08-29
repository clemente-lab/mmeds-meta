#!/usr/bin/python

import pandas as pd
import mmeds.config as fig
from glob import glob
from random import randrange, getrandbits
from pathlib import Path


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
        for key, item in mmeds_meta.items():
            new_line.append(str(item[row]))
        lines.append('\t'.join(new_line))
    Path(output_path).write_text('\n'.join(lines) + '\n')


def write_error_files():
    # Parser issue
    issue_parsing = df.copy(deep=True)
    for i, val in enumerate(['\t', '\n', '\r']):
        issue_parsing.loc[5 + i]['RawDataProtocol']['RawDataDatePerformed'] = val
    write_test_metadata(issue_parsing, '{}/validate_error_issue_parsing.tsv'.format(file_path))
    # Mess up the file
    with open('{}/validate_error_issue_parsing.tsv'.format(file_path), 'ab+') as f:
        f.write(bytearray(getrandbits(8) for _ in range(20)))

    # Wrong types
    wrong_type = df.copy(deep=True)
    for i in range(10):
        val = randrange(5, len(wrong_type))
        wrong_type.loc[val]['RawDataProtocol']['RawDataDatePerformed'] = 'Not A Date'
    write_test_metadata(wrong_type, '{}/validate_error_wrong_type.tsv'.format(file_path))

    # Illegal Column Header
    illegal_header = df.copy(deep=True)
    col = illegal_header[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', 'IllegalColumn_'), inplace=True)
    illegal_header = illegal_header.join(col, how='outer')
    write_test_metadata(illegal_header, '{}/validate_error_illegal_header.tsv'.format(file_path))

    # Illegal Column Header
    illegal_header = df.copy(deep=True)
    col = illegal_header[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', 'IllegalColumn_'), inplace=True)
    illegal_header = illegal_header.join(col, how='outer')
    write_test_metadata(illegal_header, '{}/validate_error_illegal_header.2.tsv'.format(file_path))

    # Illegal Column name
    column_name = df.copy(deep=True)
    col = column_name[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', 'HostSubjectId'), inplace=True)
    column_name = column_name.join(col, how='outer')
    write_test_metadata(column_name, '{}/validate_error_column_name.tsv'.format(file_path))

    # Illegal Column
    illegal_column = df.copy(deep=True)
    col = illegal_column[('Subjects', 'HostSubjectId')]
    col.rename(('Subjects', 'IllegalColumn'), inplace=True)
    illegal_column = illegal_column.join(col, how='outer')
    write_test_metadata(illegal_column, '{}/validate_error_illegal_column.tsv'.format(file_path))

    # Illegal table
    illegal_table = df.copy(deep=True)
    col = illegal_table[('Subjects', 'HostSubjectId')]
    col.rename(('IllegalTable', 'IllegalColumn'), inplace=True)
    illegal_table = illegal_table.join(col, how='outer')
    write_test_metadata(illegal_table, '{}/validate_error_illegal_table.tsv'.format(file_path))

    # Missing a column
    missing_column = df.copy(deep=True)
    missing_column.drop(('Subjects', 'HostSubjectId'), axis=1, inplace=True)
    write_test_metadata(missing_column, '{}/validate_error_missing_column.tsv'.format(file_path))

    # Missing a table
    missing_table = df.copy(deep=True)
    missing_table.drop('Subjects', axis=1, inplace=True)
    write_test_metadata(missing_table, '{}/validate_error_missing_table.tsv'.format(file_path))

    # Empty Cells
    empty_cell = df.copy(deep=True)
    for i in range(10):
        val = randrange(3, len(empty_cell))
        empty_cell.loc[val]['Subjects']['HostSubjectId'] = ''
    write_test_metadata(empty_cell, '{}/validate_error_empty_cell.tsv'.format(file_path))

    # Missing type
    missing_type = df.copy(deep=True)
    col = missing_type[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', 'NoTypeColumn'), inplace=True)
    for val in range(0, 3):
        col.loc[val] = ''
    missing_type = missing_type.join(col, how='outer')
    write_test_metadata(missing_type, '{}/validate_error_missing_type.tsv'.format(file_path))

    # Invalid type
    invalid_type = df.copy(deep=True)
    col = invalid_type[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', 'NoTypeColumn'), inplace=True)
    for val in range(0, 3):
        col.loc[val] = 'NotAType'
    invalid_type = invalid_type.join(col, how='outer')
    write_test_metadata(invalid_type, '{}/validate_error_invalid_type.tsv'.format(file_path))

    # Whitespace
    whitespace = df.copy(deep=True)
    whitespace.iloc[10][('BodySite', 'SpecimenBodySite')] = \
        ' ' + whitespace.iloc[10][('BodySite', 'SpecimenBodySite')] + ' '
    write_test_metadata(whitespace, '{}/validate_error_whitespace.tsv'.format(file_path))

    # Missing Required Value
    missing_required_value = df.copy(deep=True)
    for i in range(10):
        val = randrange(3, len(missing_required_value))
        missing_required_value.loc[val]['RawData']['RawDataID'] = 'NA'
    write_test_metadata(missing_required_value, '{}/validate_error_missing_required_value.tsv'.format(file_path))

    # Non Standard NA
    non_standard_na = df.copy(deep=True)
    for i in range(10):
        val = randrange(3, len(non_standard_na))
        non_standard_na.loc[val]['RawData']['RawDataID'] = 'n.a.'
    write_test_metadata(non_standard_na, '{}/validate_error_non_standard_na.tsv'.format(file_path))

    # Numeric Header Column
    number_header = df.copy(deep=True)
    col = number_header[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', '0'), inplace=True)
    number_header = number_header.join(col, how='outer')
    write_test_metadata(number_header, '{}/validate_error_number_header.tsv'.format(file_path))

    # na Header Column
    na_header = df.copy(deep=True)
    col = na_header[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', 'na'), inplace=True)
    na_header = na_header.join(col, how='outer')
    write_test_metadata(na_header, '{}/validate_error_na_header.tsv'.format(file_path))

    # phi Header Column
    phi_header = df.copy(deep=True)
    col = phi_header[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', 'Address'), inplace=True)
    phi_header = phi_header.join(col, how='outer')
    write_test_metadata(phi_header, '{}/validate_error_phi_header.tsv'.format(file_path))

    # duplicate Column
    duplicate_column = df.copy(deep=True)
    col = duplicate_column[('Subjects', 'HostSubjectId')]
    col.rename(('AdditionalMetaData', 'DupColumn'), inplace=True)
    duplicate_column = duplicate_column.join(col, how='outer')
    col.rename(('AdditionalMetaData', 'DupColumn.1'), inplace=True)
    duplicate_column = duplicate_column.join(col, how='outer')
    write_test_metadata(duplicate_column, '{}/validate_error_duplicate_column.tsv'.format(file_path))

    # duplicate value
    duplicate_value = df.copy(deep=True)
    duplicate_value.iloc[10]['Subjects']['HostSubjectId'] = duplicate_value.iloc[11]['Subjects']['HostSubjectId']
    write_test_metadata(duplicate_value, '{}/validate_error_duplicate_value.tsv'.format(file_path))

    # different_length
    different_length = df.copy(deep=True)
    different_length.iloc[10]['RawData']['BarcodeSequence'] =\
        different_length.iloc[10]['RawData']['BarcodeSequence'][:5]
    write_test_metadata(different_length, '{}/validate_error_different_length.tsv'.format(file_path))

    # invalid_barcodesequence
    invalid_barcodesequence = df.copy(deep=True)
    invalid_barcodesequence.iloc[10]['RawData']['BarcodeSequence'] =\
        invalid_barcodesequence.iloc[10]['RawData']['BarcodeSequence'][:-1] + 'J'
    write_test_metadata(invalid_barcodesequence, '{}/validate_error_invalid_barcodesequence.tsv'.format(file_path))

    # invalid_icd_code
    invalid_icd_code = df.copy(deep=True)
    invalid_icd_code.iloc[10]['ICDCode']['ICDCode'] = 'NotACode'
    write_test_metadata(invalid_icd_code, '{}/validate_error_invalid_icd_code.tsv'.format(file_path))

    # Multiple Studies in a single metadata file
    multiple_studies = df.copy(deep=True)
    if i in range(5, 10):
        multiple_studies.iloc[10]['Study']['StudyName'] = 'OtherStudy'
    write_test_metadata(multiple_studies, '{}/validate_error_multiple_studies.tsv'.format(file_path))

    # invalid_date range
    invalid_date_range = df.copy(deep=True)
    invalid_date_range.iloc[10]['Intervention']['InterventionStartDate'] = '2012-05-1'
    invalid_date_range.iloc[10]['Intervention']['InterventionEndDate'] = '2011-05-1'
    write_test_metadata(invalid_date_range, '{}/validate_error_invalid_date_range.tsv'.format(file_path))

    # future_date
    future_date = df.copy(deep=True)
    future_date.iloc[10]['ResultsProtocol']['ResultsDatePerformed'] = '2222-2-1'
    write_test_metadata(future_date, '{}/validate_error_future_date.tsv'.format(file_path))

    # Length error
    cell_length = df.copy(deep=True)
    cell_length.iloc[10]['ResultsProtocol']['ResultsProcessor'] = 'asdf' * 40
    write_test_metadata(cell_length, '{}/validate_error_cell_length.tsv'.format(file_path))


def write_warning_files():
    # stddev_warning
    stddev_warning = df.copy(deep=True)
    stddev_warning.iloc[10]['Subjects']['BirthYear'] = '9'
    write_test_metadata(stddev_warning, '{}/validate_warning_stddev_warning.tsv'.format(file_path))

    # categorical_data
    categorical_data = df.copy(deep=True)
    categorical_data.iloc[10]['ResultsProtocols']['ResultsMethod'] = 'Protocol90'
    write_test_metadata(categorical_data, '{}/validate_warning_categorical_data.tsv'.format(file_path))


if __name__ == '__main__':

    df = pd.read_csv(fig.TEST_METADATA, sep='\t', header=[0, 1], na_filter=False)
    test_files = []
    file_path = '/home/david/Work/mmeds-meta/mmeds/test_files/validation_files/'
    for test_file in glob(file_path + 'validate_*'):
        print('Deleting {}'.format(test_file))
        Path(test_file).unlink()

    write_error_files()
    write_warning_files()
