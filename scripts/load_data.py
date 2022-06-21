import click
from shutil import unpack_archive
from pathlib import Path

import mmeds.util as util
import mmeds.config as fig

"""
Script that takes in a zip file of sequencing runs, studies, and analysis configs made from dump_data.py,
    and uploads them back into MMEDS through the watcher
"""

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--input-zip', required=True, help='Input zip file generated from dump_data.py')
def load(input_zip):
    # Unzip archive
    zip_path = Path(input_zip)
    unpack_archive(input_zip, zip_path.parent)

    # Store top level unzipped dirs
    unzipped_path = zip_path.parent / zip_path.stem
    studies_path = unzipped_path / "studies"
    runs_path = unzipped_path / "sequencing_runs"

    # Upload sequencing runs
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
        util.upload_sequencing_run_directly(run.name, fig.REUPLOAD_USER, paths, reads_type, barcodes_type)


if __name__ == '__main__':
    load()
