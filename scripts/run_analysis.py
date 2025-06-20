#!/usr/bin/env python3

import click
from pathlib import Path
from subprocess import run, CalledProcessError
from mmeds.summary import summarize_qiime
from mmeds.database.database import Database
from mmeds.spawn import Watcher
from mmeds.util import setup_environment, run_analysis, start_analysis_local
import mmeds.config as fig

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='0.1')
@click.option('-s', '--study-name', required=True,
              help='Name of study on which to perform analysis')
@click.option('-n', '--analysis-name', required=True,
              help='Name of new analysis')
@click.option('-t', '--workflow_type', required=True,
              help='Type of analysis to perform')
@click.option('-u', '--user', required=True,
              help='Owner of the study')
@click.option('-c', '--config', required=False,
              help='analysis config yaml file')
def run_analysis(study_name, analysis_name, workflow_type, user, config):
    """
    Submits an analysis process for running on a study
    """
    q = get_queue()
    runs = {}
    analysis_type = 'default'
    with Database(testing=fig.TESTING) as db:
        access_code = db.get_access_code_from_study_name(study_name, user)
        files, path = db.get_mongo_files(access_code, False)
        if "sequencing_runs" in fig.WORKFLOWS[workflow_type]["parameters"]:
            runs = db.get_sequencing_run_locations(files['metadata'], user)
            analysis_type = 'dada2'
    ret = start_analysis_local(q, access_code, analysis_name, workflow_type, user, config, runs, analysis_type)
    assert ret == 0

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
