#!/usr/bin/python

import click
import shutil
import pandas as pd
import mmeds.config as fig
from mmeds.util import join_metadata, write_metadata, load_metadata
from random import randrange, getrandbits
from pathlib import Path
import numpy as np
import datetime as dt

__author__ = "Adam Cantor"
__copyright__ = "Copyright 2021, The Clemente Lab"
__credits__ = ["Adam Cantor", "Jose Clemente"]
__license__ = "GPL"


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-p', '--path', default='../test_files/', show_default=True,
        type=click.Path(exists=True), help='Path to put the created test files')

def main(path):
    file_path = Path(path) / 'validation_files'
    print('Output:', file_path)
    for test_file in file_path.glob('validate_*'):
        print('Deleting {}'.format(test_file))
        test_file.unlink()

    # Create the subjects' test files
    sub_df = pd.read_csv(fig.TEST_SUBJECT_SHORT, sep='\t', header=[0,1], na_filter=False)
    write_error_files(sub_df, 'subject', file_path)

    #Create the specimens' test files
    spec_df = pd.read_csv(fig.TEST_SPECIMEN_SHORT, sep='\t', header=[0,1], na_filter=False)
    write_error_files(spec_df, 'specimen', file_path)

def write_test_metadata(df, output_path, output_name):
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
    output = Path(output_path)
    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)
    output = Path(output_path) / output_name
    if not output.exists():
        output.touch()
    print("writing", output_name)
    output.write_text('\n'.join(lines) + '\n')


def write_error_files(df, file_type, file_path):
    # Get headers and prepare replacement length
    headers = df.columns
    headerCount = 3
    diff = len(df) - headerCount

    # Blank data columns
    for header in headers:
        blank_column = df.copy(deep=True)
        blank_column.loc[headerCount:len(df), header] = np.array([''] * diff)
        write_test_metadata(blank_column, file_path / 'blank_column_tests' / file_type, f'blank_{header[1]}.tsv')

    # NA data columns
    for header in headers:
        na_column = df.copy(deep=True)
        na_column.loc[headerCount:len(df), header] = np.array(['NA'] * diff)

        write_test_metadata(na_column, file_path / 'na_column_tests' / file_type, f'na_{header[1]}.tsv')

    # Other data columns
    for header in headers:
        other_column = df.copy(deep=True)
        # Get another column, ensure it is not the same as being tested
        while True:
            other_header = headers[randrange(len(headers))]
            if not other_header == header:
                break

        other_column.loc[headerCount:len(df), header] = df.loc[headerCount:len(df), other_header]

        write_test_metadata(other_column, file_path / 'other_column_tests' / file_type, f'other_{header[1]}.tsv')

    # Numbers data columns
    for header in headers:
        number_column = df.copy(deep=True)
        number_column.loc[headerCount:len(df), header] = np.array([randrange(2000) for i in range(diff)])

        write_test_metadata(number_column, file_path / 'number_column_tests' / file_type, f'number_{header[1]}.tsv')

    # Dates data columns
    for header in headers:
        date_column = df.copy(deep=True)
        date_column.loc[headerCount:len(df), header] = np.array([dt.date(randrange(2015, 2026), randrange(1, 13), randrange(1, 29)) for i in range(diff)])

        write_test_metadata(date_column, file_path / 'date_column_tests' / file_type, f'date_{header[1]}.tsv')


if __name__ == '__main__':
    main()
