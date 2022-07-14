import click
from pathlib import Path
from shutil import make_archive

import mmeds.util as util


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--input-study-names', required=True, help='Text file with list of study directories to include')
@click.option('-p', '--path', required=False, default='.', help='Base path that includes study directories')
@click.option('-o', '--output-zip', required=False, default='mmeds_dump', help='Name for output zip file')
@click.option('-u', '--user', required=False, default='adamcantor22', help='Account that owns the used runs')
@click.option('-nz', '--no-zip', required=False, is_flag=True, help='Whether or not to zip the final structure')
def dump(input_study_names, path, output_zip, user, no_zip):
    """
    Script that collects data about a study or studies, and their associated sequencing runs and analysis configs,
        and converts it into a ZIP archive that can be read back into MMEDS using load_data.py
    """

    # Grab study directories from input file, stripping newlines and blank lines
    study_dirs = []
    head = Path(path)
    with open(input_study_names, 'r') as f:
        for line in f.readlines():
            d = line.strip('\n')
            if not d == '':
                study_dirs.append(head / d)

    # Confirm study paths exist
    head = Path(path)
    for study in study_dirs:
        if not study.is_dir():
            print(f"{study} is not a valid directory")
            return False

    # Get metadata, sequencing runs, and analysis configs
    directory_info = util.get_study_components(study_dirs)

    # Compile sequencing runs with no duplicates
    all_runs = []
    for study in directory_info:
        for run in directory_info[study]['runs']:
            if run not in all_runs:
                all_runs.append(run)

    # Get sequencing run locations
    run_locations = util.get_sequencing_run_locations(all_runs)

    # Create file structure to be zipped
    zip_path = head / output_zip
    try:
        zip_path.mkdir()
    except FileExistsError:
        print("Zip folder already exists")
        return False

    # Populate dump directory and assert OK
    result = util.populate_dump_dir(run_locations, directory_info, zip_path)
    assert result == 0

    # Zip up archive
    if not no_zip:
        make_archive(str(zip_path), 'zip', root_dir=head, base_dir=output_zip)
    print("done")


if __name__ == '__main__':
    dump()
