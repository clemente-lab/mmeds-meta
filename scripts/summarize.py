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
@click.option('-c', '--config_file', required=False,
              default=None, type=click.Path(exists=True),
              help='Path to configuration file for analysis.')
@click.option('-l', '--load_info', required=False,
              help='Commands to run before scripts to load modules/environments')
def run_summarize(file_index, tool_type, path, load_info, config_file):
    # Load the files
    config_file = Path(config_file)
    path = Path(path)
    files = {}
    lines = (path / 'file_index.tsv').read_text().strip().split('\n')
    for line in lines:
        parts = line.split('\t')
        files[parts[0]] = Path(parts[1])

    # Create the summary directory
    if not files['summary'].is_dir():
        files['summary'].mkdir()

    summarize_qiime(path, files, load_info, config_file, tool_type)


if __name__ == "__main__":
    run_summarize()
