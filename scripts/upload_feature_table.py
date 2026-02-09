#!/usr/bin/env python3

import click
import mmeds.util as util
from mmeds.spawn import Watcher
from pathlib import Path

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-n', '--table-name', required=True, help='Name of table')
@click.option('-t', '--table-type', required=True, help='Type of table', default="taxonomic")
@click.option('-f', '--table-file', required=True, help='Filepath containing table')
@click.option('-s', '--study', required=True, help='Study to be associated with feature table')
@click.option('-u', '--user', required=True, help='User for upload')
def upload_sequencing_run(table_name, table_type, table_file, study, user):
    """
    Uploads a sequencing run directly from the command line, bypassing the server
    """
    q = get_queue()

    result = util.upload_feature_table_local(q, user, study, table_name, table_type, table_file)
    assert result == 0


def get_queue():
    """ Connects to a watcher queue to be sent to the analysis function in util.py. Those functions
    cannot connect to Watcher queue on their own due to their needing a recursive import
    """
    watcher = Watcher()
    watcher.connect()
    queue = watcher.get_queue()
    return queue


if __name__ == '__main__':
    upload_sequencing_run()
