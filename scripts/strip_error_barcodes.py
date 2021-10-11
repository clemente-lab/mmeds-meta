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
@click.option('-m', '--mapping-file', required=True, help='Path to the mapping file')
@click.option('-i', '--input-dir', required=True, help='Directory with fastq.gz files')
@click.option('-o', '--output-dir', required=True, help='Directory to output new fastq.gz files to')
def strip_errors(num_allowed_errors, mapping_file, input_dir, output_dir):
    """
    Method to strip reads from individual demultiplexed fastq.gz files if a read has
    barcode error greater than N (num_allowed_errors) and write to output
    """

    # Get mapping file as DataFrame and save sample data to hash
    map_df = pd.read_csv(Path(mapping_file), sep='\t', header=[0], na_filter=False)
    map_hash = {}

    for i in range(len(map_df['#SampleID'])):
        if i > 0:
            map_hash[map_df['#SampleID'][i]] = \
                    (
                            map_df['BarcodeSequence'][i],
                            map_df['BarcodeSequenceR'][i]
                    )
    strip_error_barcodes(num_allowed_errors, map_hash, input_dir, output_dir)


if __name__ == '__main__':
    strip_errors()
