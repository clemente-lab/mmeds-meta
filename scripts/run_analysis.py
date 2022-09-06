#!/usr/bin/env python3

import click
from pathlib import Path
from subprocess import run, CalledProcessError
from mmeds.summary import summarize_qiime
from mmeds.database.database import Database
from mmeds.spawn import Watcher
from mmeds.util import setup_environment, run_analysis, start_analysis_local

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='0.1')
@click.option('-n', '--study-name', required=True,
              help='Name of study on which to perform analysis')
@click.option('-t', '--tool_type', required=True,
              help='Type of tools to perform summary for')
@click.option('-u', '--user', required=True,
              help='Owner of the study')
@click.option('-c', '--config', required=False,
              help='analysis config yaml file')
def run_analysis(study_name, tool_type, user, config):
    """
    Checks the number of reads per sample in a multiplexed file.
    """
    q = get_queue()
    with Database(testing=True) as db:
        access_code = db.get_access_code_from_study_name(study_name, user)
    ret = start_analysis_local(q, access_code, tool_type, user, config)

    assert ret == 0

    #run_analysis()
    #summarize_qiime(f'{path}/Qiime2_0/summary', tool_type)


def get_queue():
    """ Creates a watcher queue to be sent to the analysis function in util.py. Those functions
    cannot create their own Watcher queue due to their needing a recursive import
    """
    watcher = Watcher()
    watcher.connect()
    queue = watcher.get_queue()
    return queue

if __name__ == '__main__':
    run_analysis()
