import click
from pathlib import Path
from shutil import copy, make_archive
import pandas as pd

import mmeds.config as fig

"""
Script that collects data about a study or studies, and their associated sequencing runs and analysis configs,
    and converts it into a ZIP archive that can be read back into MMEDS using load_data.py
"""

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--input-study-names', required=True, help='Text file with list of study directories to include')
@click.option('-p', '--path', required=False, default='.', help='Base path that includes study directories')
@click.option('-o', '--output-zip', required=False, default='mmeds_dump', help='Name for output zip file')
@click.option('-u', '--user', required=False, default='adamcantor22', help='Account that owns the used runs')
@click.option('-nz', '--no-zip', required=False, is_flag=True, help='Whether or not to zip the final structure')
def dump(input_study_names, path, output_zip, user, no_zip):
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
            return

    # Loop through each included study and collect:
    #   -subject/specimen metadata
    #   -used sequencing runs
    #   -analysis configs
    directory_info = {}
    for study in study_dirs:
        directory_info[study] = {}

        # Get subject file
        subj = list(study.glob("*subj*"))
        if not len(subj) == 1:
            print(f"Found {len(subj)} in {study} with name 'subj', need exactly 1")
            return
        directory_info[study]['subject'] = subj[0]

        # Get specimen file
        spec = list(study.glob("*spec*"))
        if not len(spec) == 1:
            print(f"Found {len(spec)} in {study} with name 'spec', need exactly 1")
            return
        directory_info[study]['specimen'] = spec[0]

        # Collect names of used sequencing runs
        runs = []
        df = pd.read_csv(directory_info[study]['specimen'], sep='\t', header=[0, 1], skiprows=[2, 3, 4])
        for run in df['RawDataProtocol']['RawDataProtocolID']:
            if run not in runs:
                runs.append(run)
        directory_info[study]['runs'] = runs
        directory_info[study]['name'] = df['Study']['StudyName'][0]

        # Collect analysis configs
        configs = []
        # TODO: Allow for analysis tools other than Qiime2?
        analyses = list(study.glob("*Qiime2*"))
        for a in analyses:
            config = a / "config_file.yaml"
            if not config.is_file():
                print(f"No configuration file found for study {study} in analysis {a}")
                return
            configs.append(config)
        directory_info[study]['configs'] = configs

    # Compile sequencing runs with no duplicates
    all_runs = []
    for study in directory_info:
        for run in directory_info[study]['runs']:
            if run not in all_runs:
                all_runs.append(run)

    # Get sequencing run locations
    run_locations = {}
    for run in all_runs:
        dirs = list(Path(fig.SEQUENCING_DIR).glob(f"*{run}*"))
        if len(dirs) == 0:
            print(f"No sequencing run directory for run {run}")
            return
        if len(dirs) > 1:
            for d in dirs:
                if user in str(d) and str(d).endswith(f"{run}_0"):
                    dirs = [d]
                    break
        run_locations[run] = dirs[0]

    # Create file structure to be zipped
    zip_path = head / output_zip
    try:
        zip_path.mkdir()
    except FileExistsError:
        print("Zip folder already exists")
        return

    runs_path = zip_path / "sequencing_runs"
    runs_path.mkdir()

    studies_path = zip_path / "studies"
    studies_path.mkdir()

    # Populate sequencing run directory
    for run in run_locations:
        run_path = runs_path / run
        run_path.mkdir()

        # Copy each datafile and directory file to zip path
        for f in run_locations[run].glob("*"):
            if not Path(f).is_dir():
                to_file = run_path / f.name
                copy(f, to_file)

    # Populate study directory
    for study in directory_info:
        study_path = studies_path / directory_info[study]['name']
        study_path.mkdir()

        # Copy each metadata file to zip path
        subj_dest = study_path / "subject.tsv"
        spec_dest = study_path / "specimen.tsv"
        copy(directory_info[study]['subject'], subj_dest)
        copy(directory_info[study]['specimen'], spec_dest)

        # Copy config files to zip path
        for i, config in enumerate(directory_info[study]['configs']):
            config_path = study_path / f"config_file_{i}.yaml"
            copy(config, config_path)

    # Zip up archive
    if not no_zip:
        make_archive(str(zip_path), 'zip', root_dir=head, base_dir=output_zip)
    print("done")


if __name__ == '__main__':
    dump()
