#!/usr/bin/env python3

import click
from mmeds.summary import summarize_qiime

__author__ = "David Wallach"
__copyright__ = "Copyright 2018, The Clemente Lab"
__credits__ = ["David Wallach", "Jose Clemente"]
__license__ = "GPL"
__maintainer__ = "David Wallach"
__email__ = "d.s.t.wallach@gmail.com"


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-p', '--path', required=False,
              type=click.Path(exists=True),
              help='Path to analysis directory')
@click.option('-l', '--load_info', required=True,
              help='Commands to run before scripts to load modules/environments')
@click.option('-c', '--config_file', required=True,
              default=None, type=click.Path(exists=True),
              help='Path to configuration file for analysis.')
@click.option('-t', '--tool_type', required=False,
              help='Type of tools to perform summary for')
def run_summarize(path, load_info, config_file, tool_type):
    summarize_qiime(path, load_info, config_file, tool_type)


if __name__ == "__main__":
    run_summarize()
