#!/usr/bin/env python3

import click
import pandas as pd
from pathlib import Path

from mmeds.util import validate_demultiplex

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='0.1')
@click.option('-d', '--data_dir',
              help="path to reverse reads multiplexed file")
@click.option('-m', '--map_path',
              required=True,
              help="Full path to a qiime2 mapping file")
@click.option('-fb', '--forward_barcodes',
              help="path to forward barcodes file.")
@click.option('-rb', '--reverse_barcodes',
              help="path to reverse barcodes file")
@click.option('-o', '--output_dir',
              help="path to reverse barcodes file")
def validate_demux(data_dir,
                   map_path,
                   forward_barcodes,
                   reverse_barcodes,
                   output_dir):
    """
    Checks the number of reads per sample in a multiplexed file.
    """
    # Create output folder
    output_dir = Path(output_dir)
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    # map_df = pd.read_csv(map_path, sep="\t", skiprows=[0, 2, 3, 4])

    # parse barcode files
    for demux_file in Path(data_dir).glob('*.fastq.*'):
        is_gzip = '.gz' in Path(demux_file).suffixes
        print(f'is gzip: {is_gzip}')
        if is_gzip:
            demux_file = str(demux_file).replace('.gz', '')
        validate_demultiplex(demux_file, forward_barcodes,
                             reverse_barcodes, map_path, output_dir, is_gzip, True)


if __name__ == '__main__':
    validate_demux()
