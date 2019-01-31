#!/usr/bin/env python3

import click
from pathlib import Path
from mmeds.summary import summarize_qiime2, summarize_qiime1

__author__ = "David Wallach"
__copyright__ = "Copyright 2018, The Clemente Lab"
__credits__ = ["David Wallach", "Jose Clemente"]
__license__ = "GPL"
__maintainer__ = "David Wallach"
__email__ = "d.s.t.wallach@gmail.com"


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--file_index', required=False,
              type=click.Path(exists=True),
              help='File containing the information about file locations')
@click.option('-t', '--tool_type', required=False,
              help='Type of tools to perform summary for')
@click.option('-p', '--path', required=False,
              type=click.Path(exists=True),
              help='Path to analysis directory')
@click.option('-m', '--metadata', required=False,
              help='List of metadata fields to analyze')
@click.option('-l', '--load_info', required=False,
              help='Commands to run before scripts to load modules/environments')
@click.option('-s', '--sampling_depth', required=False,
              help='Commands to run before scripts to load modules/environments')
def run_summarize(file_index, tool_type, path, metadata, load_info, sampling_depth):
    path = Path(path)
    # Load the files
    files = {}
    lines = (path / 'file_index.tsv').read_text().strip().split('\n')
    for line in lines:
        parts = line.split('\t')
        files[parts[0]] = Path(parts[1])

    metadata = metadata.split(',')

    if tool_type == 'qiime1':
        summarize_qiime1(path, files, metadata, load_info, sampling_depth)
    elif tool_type == 'qiime2':
        summarize_qiime2(path, files, metadata, load_info)


if __name__ == "__main__":
    run_summarize()
