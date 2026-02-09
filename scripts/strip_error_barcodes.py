#!/user/bin/env python3

import click
import os
import gzip
import pandas as pd
from pathlib import Path
from mmeds.util import strip_error_barcodes

__author__ = "Adam Cantor"
__copyright__ = "Copyright 2021 Clemente Lab"
__credits__ = ["Adam Cantor", "Jose Clemente"]
__license__ = "GPL"

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-n', '--num-allowed-errors', default=1, type=int,
              help='The number of allowed barcode errors, barcodes with more errors than this will be removed.')
@click.option('-m', '--m-mapping-file', required=True, help='Path to the mapping file')
@click.option('-i', '--i-directory', required=True, help='Directory with fastq.gz input files')
@click.option('-o', '--o-directory', required=True, help='Directory to output new fastq.gz files to')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output to stdout')
def strip_errors(num_allowed_errors, m_mapping_file, i_directory, o_directory, verbose):
    """
    Calls function to strip reads from individual demultiplexed fastq.gz files if a
    read has a barcode error greater than N (num_allowed_errors) and write to output files
    """
    strip_error_barcodes(num_allowed_errors, m_mapping_file, i_directory, o_directory, verbose)


if __name__ == '__main__':
    strip_errors()
