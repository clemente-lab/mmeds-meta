#!/usr/bin/env python3

import click
import mmeds.util as util
from mmeds.spawn import Watcher
from pathlib import Path

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-n', '--sequencing-run-name', required=True, help='Name for new sequencing run')
@click.option('-fr', '--forward-reads', required=True, help='Forward reads fastq.gz')
@click.option('-rr', '--reverse-reads', required=False, help='Reverse reads fastq.gz')
@click.option('-fb', '--forward-barcodes', required=True, help='Forward barcodes fastq.gz')
@click.option('-rb', '--reverse-barcodes', is_flag=False, help='Reverse barcodes fastq.gz')
@click.option('-u', '--user', required=True, help='User for upload')
def upload_sequencing_run(sequencing_run_name, forward_reads, reverse_reads, forward_barcodes, reverse_barcodes, user):
    """
    Uploads a sequencing run directly from the command line, bypassing the server
    """
    q = get_queue()

    datafiles = {'forward': str(Path(forward_reads).resolve())}
    if reverse_reads:
        reads_type = 'paired_end'
        datafiles['reverse'] = str(Path(reverse_reads).resolve())
    else:
        reads_type = 'single_end'

    if reverse_barcodes:
        barcodes_type = 'dual_barcodes'
        datafiles['for_barcodes']: str(Path(forward_barcodes).resolve())
        datafiles['rev_barcodes'] = str(Path(reverse_barcodes).resolve())
    else:
        datafiles['barcodes']: str(Path(forward_barcodes).resolve())
        barcodes_type = 'single_barcodes'

    result = util.upload_sequencing_run_local(q, sequencing_run_name, user, datafiles, reads_type, barcodes_type)
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
    upload_sequencing_run()
