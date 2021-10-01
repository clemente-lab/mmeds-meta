#!/usr/bin/env python3

import click
import pandas as pd
from pathlib import Path
from Bio.Seq import Seq

from mmeds.util import parse_barcodes

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='0.1')
@click.option('-f', '--forward_read',
              help="path to forward reads multiplexed file")
@click.option('-r', '--reverse_read',
              help="path to reverse reads multiplexed file")
@click.option('-o', '--output_folder',
              required=True,
              help="Output folder for results tsv files.")
@click.option('-m', '--map_path',
              required=True,
              help="Full path to a qiime2 mapping file")
@click.option('-fb', '--forward_barcodes',
              help="path to forward barcodes file.")
@click.option('-rb', '--reverse_barcodes',
              help="path to reverse barcodes file")
def test_barcodes(forward_read,
                  reverse_read,
                  output_folder,
                  map_path,
                  forward_barcodes,
                  reverse_barcodes):
    """
    Checks the number of reads per sample in a multiplexed file.
    """
    # Create output folder
    output_dir = Path(output_folder)
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    map_df = pd.read_csv(map_path, sep="\t", skiprows=[0, 2, 3, 4])

    # parse barcode files
    results_dict, full_dict = parse_barcodes(forward_barcodes, reverse_barcodes,
                                             map_df['BarcodeSequence'].tolist(), map_df['BarcodeSequenceR'].tolist())

    # Ouput read counts for only barcodes matched to in the mapping file
    results_table = pd.DataFrame.from_dict(results_dict, orient='index')
    results_table.reset_index(inplace=True)
    df_path = Path(output_folder) / 'matched_barcodes.tsv'
    results_table.to_csv((str(df_path)), index=None, header=True, sep='\t')

    # Output read counts for all barcodes
    full_table = pd.DataFrame.from_dict(full_dict, orient='index')
    full_table.reset_index(inplace=True)
    df_path = Path(output_folder) / 'all_barcodes.tsv'
    results_table.to_csv((str(df_path)), index=None, header=True, sep='\t')


if __name__ == '__main__':
    test_barcodes()
