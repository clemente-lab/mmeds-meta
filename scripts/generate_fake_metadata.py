import pandas as pd
import mmeds.config as fig
import click
from shutil import copyfile
from collections import defaultdict
from mmeds.util import write_metadata, load_metadata
from random import randrange, choice
from pathlib import Path

# List of people to generate metadata for
people = [
    'Jose',
    'Alba',
    'Tiffany',
    'Brooke',
    'Matt',
    'Hilary',
    'David',
    'Kevin',
    'Jakleen'
]
__author__ = "David Wallach"
__copyright__ = "Copyright 2021, The Clemente Lab"
__credits__ = ["David Wallach", "Jose Clemente"]
__license__ = "GPL"
__maintainer__ = "David Wallach"
__email__ = "d.s.t.wallach@gmail.com"


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-p', '--path', required=True, type=click.Path(exists=True),
              help='Path to put the created test files')
@click.option('-u', '--users', required=True, type=str,
              help='Comma separated list of names to generate metadata for')
def generate(path, users):
    subject_count = 0
    specimen_count = 0

    people = users.split(',')
    for peep in people:
        peep_path = path / peep
        if not peep_path.is_dir():
            peep_path.mkdir()
        copyfile('/home/david/Work/mmeds-meta/test_files/test_otu_table.txt', peep_path / 'test_otu_table.txt')

        # Create the subjects test files
        tdf = load_metadata(fig.TEST_SUBJECT_SHORT)
        pdf = generate_subject(tdf, peep, subject_count)
        write_test_metadata(pdf, peep_path / f'{peep}_subject.tsv', 'subject')

        df = load_metadata(fig.TEST_SPECIMEN_SHORT)
        sdf = generate_specimen(df, peep, subject_count, specimen_count)
        write_test_metadata(sdf, peep_path / f'{peep}_specimen.tsv', 'specimen')

        ali_table = generate_aliquot_id_request(peep, sdf[('Specimen', 'SpecimenID')])
        write_table(ali_table, peep_path / 'aliquot_id_request.tsv')

        sam_table = generate_sample_id_request(peep, sdf[('Aliquot', 'AliquotID')])
        write_table(sam_table, peep_path / 'sample_id_request.tsv')

        subject_count += len(tdf)
        specimen_count += len(df)


# Subjects Metadata Test Files
def write_test_metadata(df, output_path, metadata_type):
    """
    Write a dataframe or dictionary to a mmeds format metadata file.
    ================================================================
    :df: A pandas dataframe or python dictionary formatted like mmeds metadata
    :output_path: The path to write the metadata to
    """
    # Get the extra headers from the test files
    if metadata_type == 'subject':
        rdf = pd.read_csv(fig.TEST_SUBJECT_SHORT, sep='\t', header=[0, 1], na_filter=False).to_dict('list')
        length = len(df[('Subjects', 'HostSubjectId')])
    else:
        rdf = pd.read_csv(fig.TEST_SPECIMEN_SHORT, sep='\t', header=[0, 1], na_filter=False).to_dict('list')
        length = len(df[('AdditionalMetaData', 'SubjectIdCol')])

    if isinstance(df, pd.DataFrame):
        mmeds_meta = df.to_dict('list')
    else:
        mmeds_meta = df

    # Create the header lines
    lines = ['\t'.join([key[0] for key in mmeds_meta.keys()]),
             '\t'.join([key[1] for key in mmeds_meta.keys()]),
             '\t'.join([rdf[key][0] for key in rdf.keys()]),
             '\t'.join([rdf[key][1] for key in rdf.keys()]),
             '\t'.join([rdf[key][2] for key in rdf.keys()]),
             ]

    for row in range(length):
        new_line = []
        for item in mmeds_meta.values():
            new_line.append(str(item[row]))
        lines.append('\t'.join(new_line))
    output = Path(output_path)
    if not output.exists():
        output.touch()
    Path(output_path).write_text('\n'.join(lines) + '\n')


def generate_subject(df, peep, subject_count):
    """ Create the metadata for an individual """
    hosts = [subject_count + int(ID) for ID in df['Subjects']['HostSubjectId']]
    print(hosts)
    result = df.to_dict('list')
    result.update({('Subjects', 'HostSubjectId'): hosts})
    print(result[('Subjects', 'HostSubjectId')])
    return result


def generate_specimen(df, peep, subject_count, specimen_count):
    new_cols = {}
    new_cols[('AdditionalMetaData', 'SubjectIdCol')] =\
        [subject_count + int(ID) for ID in df['AdditionalMetaData']['SubjectIdCol']]

    print(new_cols[('AdditionalMetaData', 'SubjectIdCol')])
    new_cols[('Study', 'StudyName')] = [f'{peep}_Study'] * len(df)
    new_cols[('Specimen', 'SpecimenID')] = [f'Specimen{specimen_count + count}' for count in range(len(df))]
    new_cols[('Aliquot', 'AliquotID')] =\
        [f'{spec}-Aliquot{count}' for count, spec in enumerate(new_cols[('Specimen', 'SpecimenID')])]
    new_cols[('Sample', 'SampleID')] = [f'{spec}-Sample{count}' for count, spec in
                                        enumerate(new_cols[('Aliquot', 'AliquotID')])]
    result = df.to_dict('list')
    result.update(new_cols)
    return result


def generate_aliquot_id_request(peep, specimen_ids):
    table = defaultdict(list)
    for _ in specimen_ids:
        table['StudyName'].append(f'{peep}_Study')
        # Random Specimen
        table['SpecimenID'].append(choice(specimen_ids))
        table['AliquotWeight'].append(float(randrange(1, 9)) / float(randrange(2, 10)))
    return table


def generate_sample_id_request(peep, aliquot_ids):
    table = defaultdict(list)
    dates = ['2020-03-01', '2021-02-12', '1999-06-23']
    versions = ['0.3.0', '1.0.1', '1.3.0']
    tools = ['Illumina', 'GenBank', 'GreenGenes']
    conditions = ['Normal', 'Exceptional', 'Subpar']
    protocol = ['Nothing to report', 'Something to report', 'A lot to report']
    for ali in aliquot_ids:
        table['StudyName'].append(f'{peep}_Study')
        table['SampleProcessor'].append(peep)
        # Random Aliquot
        table['AliquotID'].append(choice(aliquot_ids))
        table['SampleToolVersion'].append(choice(versions))
        table['SampleTool'].append(choice(tools))
        table['SampleConditions'].append(choice(conditions))
        table['SampleDatePerformed'].append(choice(dates))
        table['SampleProtocolInformation'].append(choice(protocol))
        table['SampleProtocolID'].append(people.index(peep))

    return table


def write_table(table, output_path):
    lines = ['\t'.join([key for key in table.keys()])]
    length = len(table['StudyName'])
    for row in range(length):
        new_line = []
        for item in table.values():
            new_line.append(str(item[row]))
        lines.append('\t'.join(new_line))

    output = Path(output_path)
    if not output.exists():
        output.touch()
    Path(output_path).write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    generate()
