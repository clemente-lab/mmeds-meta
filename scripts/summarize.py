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
@click.option('-t', '--tool_type', required=False,
              help='Type of tools to perform summary for')
@click.option('-x', '--testing',
              required=False,
              is_flag=True,
              help='testing flag for summaries, set if not in production')
def run_summarize(path, tool_type, testing):
    summarize_qiime(path, tool_type, testing)


if __name__ == "__main__":
    run_summarize()
