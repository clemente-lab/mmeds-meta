import click
from shutil import unpack_archive
from pathlib import Path

import mmeds.util as util
import mmeds.config as fig
import mmeds.secrets as sec
from mmeds.spawn import Watcher
from mmeds.authentication import add_user


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--input-zip', required=True, help='Input zip file generated from dump_data.py')
def load(input_zip):
    """
    Script that takes in a zip file of sequencing runs, studies, and analysis configs made from dump_data.py,
        and uploads them back into MMEDS through the watcher
    """
    # Ensure the reupload user exists
    add_user(fig.REUPLOAD_USER, sec.REUPLOAD_PASS, fig.TEST_EMAIL)

    # Open watcher queue
    queue = get_queue()

    # Unzip archive
    zip_path = Path(input_zip)
    unpack_archive(input_zip, zip_path.parent)

    # Store top level unzipped dirs
    unzipped_path = (zip_path.parent / zip_path.stem).resolve()
    studies_path = unzipped_path / "studies"
    runs_path = unzipped_path / "sequencing_runs"

    # Upload sequencing runs (must be done before studies)
    result = util.process_sequencing_runs_local(runs_path, queue)
    assert result == 0

    # Upload studies
    result = util.process_studies_local(studies_path, queue)
    assert result == 0

    print("Reupload complete.")


def get_queue():
    """ Creates a watcher queue to be sent to the upload functions in util.py. Those functions
            cannot create their own Watcher queue due to their needing a recursive import
    """
    watcher = Watcher()
    watcher.connect()
    queue = watcher.get_queue()
    return queue


if __name__ == '__main__':
    load()
