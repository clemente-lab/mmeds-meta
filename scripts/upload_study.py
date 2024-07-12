#!/usr/bin/env python3

import click
import mmeds.util as util
from mmeds.spawn import Watcher

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-n', '--study-name', required=True, help='Name for new study (must match specimen entries)')
@click.option('-i', '--i-subject', required=True, help='MMEDS Subject File')
@click.option('-s', '--i-specimen', required=True, help='MMEDS Specimen File')
@click.option('-u', '--user', required=True, help='User for upload')
@click.option('-m', '--meta-study', is_flag=True, help='Flag for meta-study. Will not upload to SQL database')
def upload_study(study_name, i_subject, i_specimen, user, meta_study):
    """
    Uploads a study directly from the command line, bypassing the server
    """
    print(meta_study)
    q = get_queue()
    subject_type = util.get_subject_type(i_subject)
    result = util.upload_study_local(q, study_name, i_subject, subject_type, i_specimen, user, meta_study)
    assert result == 0


def get_queue():
    """ Creates a watcher queue to be sent to the analysis function in util.py. Those functions
    cannot create their own Watcher queue due to their needing a recursive import
    """
    watcher = Watcher()
    watcher.connect()
    queue = watcher.get_queue()
    return queue


if __name__ == '__main__':
    upload_study()
