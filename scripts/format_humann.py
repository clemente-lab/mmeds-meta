#!/usr/bin/env python3

import click
from mmeds.util import format_table_to_humann

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--i-table', required=True,
              help='TSV extracted from a Qiime2 FeatureTable')
@click.option('-m', '--metadata-file', required=True,
              help='Qiime2 formatted mapping file')
@click.option('-c', '--metadata-column', required=True, multiple=True,
              help='Metadata category to be added to feature table. Must use \'-c\' again for each additional arg')
@click.option('-r', '--remove-nans', is_flag=True, default=False,
              help="Remove samples from the output that are NaN for the any of the added metadata.")
@click.option('-a', '--add-codes', is_flag=True, default=False,
              help="For BRITE hierarchical data, add a unique code to the head of each pathway")
@click.option('-o', '--o-table', required=True,
              help='Output TSV ready for humann_barplot"')
def format_table(i_table, metadata_file, metadata_column, remove_nans, add_codes, o_table):
    """ Script that calls the format function in util.py to convert to a format that can be read by format_input.py """
    format_table_to_humann(i_table, metadata_file, metadata_column, o_table, remove_nans, add_codes)


if __name__ == '__main__':
    format_table()
