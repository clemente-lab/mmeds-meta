import click
from shutil import unpack_archive, copy
from pathlib import Path
from time import sleep
import pandas as pd

import mmeds.util as util
import mmeds.config as fig
import mmeds.secrets as sec
from mmeds.spawn import Watcher
from mmeds.authentication import add_user

"""
Script that takes in a zip file of sequencing runs, studies, and analysis configs made from dump_data.py,
    and uploads them back into MMEDS through the watcher
"""

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--input-zip', required=True, help='Input zip file generated from dump_data.py')
def load(input_zip):
    # Ensure the reupload user exists
    add_user(fig.REUPLOAD_USER, sec.REUPLOAD_PASS, fig.TEST_EMAIL)

    # Open watcher queue
    queue = get_queue()

    # Unzip archive
    zip_path = Path(input_zip)
    unpack_archive(input_zip, zip_path.parent)

    # Store top level unzipped dirs
    unzipped_path = zip_path.parent / zip_path.stem
    studies_path = unzipped_path / "studies"
    runs_path = unzipped_path / "sequencing_runs"

    # Upload sequencing runs (must be done before studies)
    for run in runs_path.glob("*"):
        # Open directory file and extract paths
        dir_file = run / fig.SEQUENCING_DIRECTORY_FILE
        paths = {}
        with open(dir_file, "r") as f:
            content = f.read().split('\n')
            for line in content:
                if ": " in line:
                    key, val = line.split(": ")
                    paths[key] = str(run / val)

        # Evaluate reads type and barcodes type
        if "reverse" in paths:
            reads_type = 'paired_end'
        else:
            reads_type = 'single_end'
        if 'rev_barcodes' in paths:
            barcodes_type = 'dual_barcodes'
        else:
            barcodes_type = 'single_barcodes'

        # Call upload sequencing run
        result = util.upload_sequencing_run_directly(queue, run.name, fig.REUPLOAD_USER,
                                                     paths, reads_type, barcodes_type)
        # Check upload was placed in queue successfully
        if not result == 0:
            print(f"Error sending sequencing run {run.name} to queue.")
            return

    # Upload studies
    for study in studies_path.glob("*"):
        # Get metadata
        subject = study / 'subject.tsv'
        specimen = study / 'specimen.tsv'
        subject_type = get_subject_type(subject)

        # Get analysis config files
        i = 0
        configs = []
        while (study / f'config_file_{i}.yaml').is_file():
            configs.append(study / f'config_file_{i}.yaml')
            i += 1

        # Call upload study
        result = util.upload_study_directly(queue, study.name, subject, subject_type, specimen, fig.REUPLOAD_USER)

        # Check upload was placed in queue successfully
        if not result == 0:
            print(f"Error sending study {study.name} to queue.")
            return

        # Wait for study upload to complete
        # TODO: This number is arbitrary and could be insufficient (very unlikely) for the upload to complete, fix.
        sleep(10)

        # The reupload can have occurred multiple times, make sure we get the most recent
        new_studies = [study.name for study in list(fig.STUDIES_DIR.glob(f"reupload_{study.name}_*"))]
        new_studies.sort()
        new_study_dir = fig.STUDIES_DIR / new_studies[-1]

        # Copy configs to new study location
        for config in configs:
            copy(config, new_study_dir)
    print("Reupload complete.")


def get_subject_type(subject):
    """ Get value from subject type column. If multiple values, return 'mixed'. """
    df = pd.read_csv(subject, sep='\t', header=[0, 1], skiprows=[2, 3, 4])
    subject_type = df['SubjectType']['SubjectType'][0]
    for sub_type in df['SubjectType']['SubjectType']:
        if not sub_type == subject_type:
            subject_type = 'mixed'
    return subject_type.lower()


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
