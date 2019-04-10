#!/usr/bin/python

import pandas as pd
import mmeds.config as fig
from glob import glob
from random import randrange
from mmeds.util import write_df_as_mmeds
from pathlib import Path


df = pd.read_csv(fig.TEST_METADATA, sep='\t', header=[0, 1], na_filter=False)

test_files = []

file_path = '/home/david/Work/mmeds-meta/mmeds/test_files/'
for test_file in glob(file_path + 'test_validate_*'):
    print('Deleting {}'.format(test_file))
    Path(test_file).unlink()

# Parser issue
issue_parsing = df.copy(deep=True)
for i in ['\t', '\n', '\r']:
    val = randrange(3, len(issue_parsing))
    issue_parsing.loc[val]['RawDataProtocol']['RawDataDatePerformed'] = i
write_df_as_mmeds(issue_parsing, '{}/test_validate_issue_parsing.tsv'.format(file_path))

# Wrong types
wrong_type = df.copy(deep=True)
for i in range(10):
    val = randrange(3, len(wrong_type))
    wrong_type.loc[val]['RawDataProtocol']['RawDataDatePerformed'] = 'Not A Date'
write_df_as_mmeds(wrong_type, '{}/test_validate_wrong_type.tsv'.format(file_path))

# Illegal Column
illegal_column = df.copy(deep=True)
col = illegal_column[('Subjects', 'HostSubjectId')]
col.rename(('Subjects', 'IllegalColumn'), inplace=True)
illegal_column = illegal_column.join(col, how='outer')
write_df_as_mmeds(illegal_column, '{}/test_validate_illegal_column.tsv'.format(file_path))

# Illegal table
illegal_table = df.copy(deep=True)
col = illegal_table[('Subjects', 'HostSubjectId')]
col.rename(('IllegalTable', 'IllegalColumn'), inplace=True)
illegal_table = illegal_table.join(col, how='outer')
write_df_as_mmeds(illegal_table, '{}/test_validate_illegal_table.tsv'.format(file_path))

# Missing a column
missing_column = df.copy(deep=True)
missing_column.drop(('Subjects', 'HostSubjectId'), axis=1, inplace=True)
write_df_as_mmeds(missing_column, '{}/test_validate_missing_column.tsv'.format(file_path))

# Missing a table
missing_table = df.copy(deep=True)
missing_table.drop('Subjects', axis=1, inplace=True)
write_df_as_mmeds(missing_table, '{}/test_validate_missing_table.tsv'.format(file_path))

# Empty Cells
empty_cell = df.copy(deep=True)
for i in range(10):
    val = randrange(3, len(empty_cell))
    empty_cell.loc[val]['Subjects']['HostSubjectId'] = ''
write_df_as_mmeds(empty_cell, '{}/test_validate_empty_cell.tsv'.format(file_path))

# Missing type
missing_type = df.copy(deep=True)
col = missing_type[('Subjects', 'HostSubjectId')]
col.rename(('AdditionalMetaData', 'NoTypeColumn'), inplace=True)
for val in range(0, 3):
    col.loc[val] = ''
missing_type = missing_type.join(col, how='outer')
write_df_as_mmeds(missing_type, '{}/test_validate_missing_type.tsv'.format(file_path))

if False:
    # Illegal Characters
    illegal_characters = df.copy(deep=True)
    for i in [';', '%', '#',  '&', '|']:
        val = randrange(3, len(illegal_characters))
        illegal_characters.loc[val]['Subjects']['HostSubjectId'] = i
    write_df_as_mmeds(illegal_characters, '{}/test_validate_illegal_characters.tsv'.format(file_path))

    # Missing columns
    missing_columns = df.copy(deep=True)
    new_cols = {col: col if not col == ('Subjects', 'HostSubjectId') else ('Subjects', '')
                for col in missing_columns.columns}
    missing_columns = missing_columns.rename(index=str, columns=new_cols)
    write_df_as_mmeds(missing_columns, '{}/test_validate_missing_columns.tsv'.format(file_path))

    # Missing tables
    missing_tables = df.copy(deep=True)
    new_cols = {col: col if not col == ('Subjects', 'HostSubjectId') else ('', 'HostSubjectId')
                for col in missing_tables.columns}
    missing_tables = missing_tables.rename(index=str, columns=new_cols)
    write_df_as_mmeds(missing_tables, '{}/test_validate_missing_tables.tsv'.format(file_path))
