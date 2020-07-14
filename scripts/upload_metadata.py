#! /usr/bin python3
from mmeds.validate import validate_mapping_file
from mmeds.util import create_local_copy
from datetime import datetime
import mmeds.config as fig
import click


# def validate_mapping_file(file_fp, metadata_type, subject_ids, subject_type, delimiter='\t'):
@click.command()
@click.option('-s', '--subject_file', required=True, type=click.Path(exists=True), help='Subject Metadata File')
@click.option('-f', '--specimen_file', required=True, type=click.Path(exists=True), help='Specimen Metadata File')
@click.option('-t', '--subject_type', default='human', help='Type of subject in metadata. "human" or "animal"')
@click.option('-u', '--uploader_name', required=True, help='Who requested this file be uploaded')
@click.option('-n', '--study_name', required=True, help='The name of the study that this relates to')
def main(subject_file, specimen_file, subject_type, uploader_name, study_name):

    # Base directory where these files will be stored
    ROOT = fig.DATABASE_DIR / 'metadata' / study_name
    if not ROOT.is_dir():
        ROOT.mkdir()

    errors, warnings, subjects = validate_mapping_file(subject_file, 'subject', None, subject_type)
    spec_errors, spec_warnings, _ = validate_mapping_file(specimen_file, 'specimen', subjects, subject_type)

    # Exit if there are any errors
    if errors + spec_errors:
        print('Subject errors')
        for error in errors:
            print(error)
        print('Specimen errors')
        for error in errors:
            print(spec_errors)
        quit()

    if warnings + spec_warnings:
        print('Subject warnings')
        for warning in warnings:
            print(warning)
        print('Specimen warnings')
        for warning in warnings:
            print(spec_warnings)
        answer = input("Proceed with warnings? [Y]/n\n")
        if answer.lower() == 'n':
            print("Aborting")
            quit()
        else:
            print("Proceeding")

    new_dir = ROOT / (datetime.now().strftime('%Y-%m-%d_%H:%M') + '_' + uploader_name)
    new_dir.mkdir()
    with open(subject_file, 'rb') as f:
        create_local_copy(f, 'subject_file', new_dir)
    with open(specimen_file, 'rb') as f:
        create_local_copy(f, 'specimen_file', new_dir)


if __name__ == "__main__":
    main()
