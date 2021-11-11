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

    # handle gzipped barcodes
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

    # run validate on each demultiplexed file in the directory
    results_dict = {}
    full_dict = {}
    for demux_file in Path(data_dir).glob('*.fastq*'):
        is_gzip = '.gz' in Path(demux_file).suffixes
        if is_gzip:
            demux_file = str(demux_file).replace('.gz', '')
        # Ignore pheniqs file of unmatched reads
        if 'undetermined' in demux_file:
            continue
        validate_output, matched_barcodes_count, all_barcodes_count = validate_demultiplex(demux_file,
                                                                                           forward_barcodes,
                                                                                           reverse_barcodes,
                                                                                           map_path,
                                                                                           output_dir,
                                                                                           is_gzip,
                                                                                           True)

        # Traceback error can occur if there's a problem with the demultiplexed file.
        if 'Traceback' in str(validate_output):
            log_file = Path(output_dir) / f'{Path(demux_file).stem}_validate_error.log'
            log_file.write_text('error validating demultiplex file')

        results_dict[f'{Path(demux_file).stem}'] = matched_barcodes_count
        full_dict[f'{Path(demux_file).stem}'] = all_barcodes_count

    # ouput read counts for only barcodes matched to in the mapping file
    results_table = pd.DataFrame.from_dict(results_dict, orient='index')
    results_table.reset_index(inplace=True)

    # output read counts for all barcodes
    full_table = pd.DataFrame.from_dict(full_dict, orient='index')
    full_table.reset_index(inplace=True)

    all_path = Path(output_dir) / 'all_barcodes.tsv'
    matched_path = Path(output_dir) / 'matched_barcodes.tsv'
    results_table.to_csv((str(matched_path)), index=None, header=True, sep='\t')
    full_table.to_csv((str(all_path)), index=None, header=True, sep='\t')

    # lastly, handle gzipping
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
