#!/usr/bin/env python3

import click
import pandas as pd
from pathlib import Path
from subprocess import run, CalledProcessError

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

    gzipped_barcodes = '.gz' in Path(forward_barcodes).suffixes
    if gzipped_barcodes:
        gunzip_forward_barcodes = ['gunzip', f'{forward_barcodes}']
        gunzip_reverse_barcodes = ['gunzip', f'{reverse_barcodes}']
        try:
            run(gunzip_forward_barcodes, capture_output=True, check=True)
            run(gunzip_reverse_barcodes, capture_output=True, check=True)
        except CalledProcessError as e:
            print(e.output)

        forward_barcodes = forward_barcodes.replace('.gz', '')
        reverse_barcodes = reverse_barcodes.replace('.gz', '')

    # parse barcode files
    for demux_file in Path(data_dir).glob('*.fastq*'):
        is_gzip = '.gz' in Path(demux_file).suffixes
        if is_gzip:
            demux_file = str(demux_file).replace('.gz', '')
        validate_demultiplex(demux_file, forward_barcodes,
                             reverse_barcodes, map_path, output_dir, is_gzip, True)

    if gzipped_barcodes:
        gzip_forward_barcodes = ['gzip', f'{forward_barcodes}']
        gzip_reverse_barcodes = ['gzip', f'{reverse_barcodes}']
        try:
            run(gzip_forward_barcodes, capture_output=True, check=True)
            run(gzip_reverse_barcodes, capture_output=True, check=True)
        except CalledProcessError as e:
            print(e.output)


if __name__ == '__main__':
    validate_demux()
