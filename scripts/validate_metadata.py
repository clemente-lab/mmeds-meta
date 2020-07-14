#! /usr/bin python3
from mmeds.validate import validate_mapping_file
import click


# def validate_mapping_file(file_fp, metadata_type, subject_ids, subject_type, delimiter='\t'):
@click.command()
@click.option('-s', '--subject_file', required=True, help='Subject Metadata File')
@click.option('-f', '--specimen_file', required=True, help='Specimen Metadata File')
@click.option('-t', '--subject_type', default='human', help='Type of subject in metadata. "human" or "animal"')
def main(subject_file, specimen_file, subject_type):
    errors, warnings, subjects = validate_mapping_file(subject_file, 'subject', None, subject_type)
    spec_errors, spec_warnings, _ = validate_mapping_file(specimen_file, 'specimen', subjects, subject_type)
    print('Subject errors')
    for error in errors:
        print(error)
    print('Specimen errors')
    for error in errors:
        print(spec_errors)

    print('Subject warnings')
    for warning in warnings:
        print(warning)
    print('Specimen warnings')
    for warning in warnings:
        print(spec_warnings)


if __name__ == "__main__":
    main()
