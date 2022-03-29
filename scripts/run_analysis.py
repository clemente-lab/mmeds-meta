#!/usr/bin/env python3

import click
from pathlib import Path
from subprocess import run, CalledProcessError
from mmeds.summary import summarize_qiime

from mmeds.util import setup_environment, run_analysis

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='0.1')
@click.option('-p', '--path', required=False,
              type=click.Path(exists=True),
              help='Path to analysis directory')
@click.option('-t', '--tool_type', required=False,
              help='Type of tools to perform summary for')
def run_analysis(path,
                 tool_type):
    """
    Checks the number of reads per sample in a multiplexed file.
    """
    run_analysis(path)
    summarize_qiime(f'{path}/Qiime2_0/summary', tool_type)


if __name__ == '__main__':
    run_analysis()
