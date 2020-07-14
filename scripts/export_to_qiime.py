#! /usr/bin python3
from mmeds.util import join_metadata, create_qiime_from_mmeds, load_metadata, write_metadata, write_mmeds_metadata
from datetime import datetime
import mmeds.config as fig
import click


# def validate_mapping_file(file_fp, metadata_type, subject_ids, subject_type, delimiter='\t'):
@click.command()
@click.option('-s', '--subject_file', required=True, type=click.Path(exists=True), help='Subject Metadata File')
@click.option('-f', '--specimen_file', required=True, type=click.Path(exists=True), help='Specimen Metadata File')
@click.option('-u', '--subject_type', default='human',
              help='Type of subject in metadata. "human" or "animal"')
@click.option('-t', '--tool_type', required=True,
              help='Type of qiime metadata to generate, either "qiime1" or "qiime2"')
@click.option('-o', '--output_file', help='Location to output the qiime metadata file')
def main(subject_file, specimen_file, subject_type, tool_type, output_file):

    subject = load_metadata(subject_file)
    specimen = load_metadata(specimen_file)

    # Merge the metadata files
    mmeds_df = join_metadata(subject, specimen, subject_type)

    write_metadata(mmeds_df, '/tmp/metadata.tsv')

    # Convert to qiime
    create_qiime_from_mmeds('/tmp/metadata.tsv',  output_file, tool_type)


if __name__ == "__main__":
    main()
