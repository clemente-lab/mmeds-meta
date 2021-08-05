#!/usr/bin/python

import click
import shutil
import pandas as pd
import mmeds.config as fig
from mmeds.util import join_metadata, write_metadata, load_metadata
from random import randrange, getrandbits
from pathlib import Path
import numpy as np
import datetime as dt

__author__ = "Adam Cantor"
__copyright__ = "Copyright 2021, The Clemente Lab"
__credits__ = ["Adam Cantor", "Jose Clemente"]
__license__ = "GPL"


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-p', '--path', required=True, type=click.Path(exists=True),
              help='Path to put the created test files')
def main(path):
    file_path = Path(path) / 'validation_files'
    print('Output: ' + str(file_path))
    for test_file in file_path.glob('validate_*'):
        print('Deleting {}'.format(test_file))
        Path(test_file).unlink()

    # Create the subjects' test files
    sub_df = pd.read_csv(Path(path) / Path(fig.TEST_SUBJECT_SHORT).name, sep='\t', header=[0,1], na_filter=False)
    write_error_files(sub_df, 'subject', file_path)

    #Create the specimens' test files
    spec_df = pd.read_csv(Path(path) / Path(fig.TEST_SPECIMEN_SHORT).name, sep='\t', header=[0,1], na_filter=False)
    write_error_files(spec_df, 'specimen', file_path)
 
def write_test_metadata(df, output_path, output_name):
    """
    Write a dataframe or dictionary to a mmeds format metadata file.
    ================================================================
    :df: A pandas dataframe or python dictionary formatted like mmeds metadata
    :output_path: The path to write the metadata to
    """
    if isinstance(df, pd.DataFrame):
        mmeds_meta = df.to_dict('list')
    else:
        mmeds_meta = df

    # Create the header lines
    lines = ['\t'.join([key[0] for key in mmeds_meta.keys()]),
             '\t'.join([key[1] for key in mmeds_meta.keys()])]

    for row in range(len(df)):
        new_line = []
        for item in mmeds_meta.values():
            new_line.append(str(item[row]))
        lines.append('\t'.join(new_line))
    output = Path(output_path)
    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)
    output = Path(output_path) / Path(output_name)
    if not output.exists():
        output.touch()
    output.write_text('\n'.join(lines) + '\n')


def write_error_files(df, file_type, file_path):
    # Contains all the headers
    # This takes up many lines and is hard-coded, not ideal
    if file_type == 'subject':
        headers = [('Ethnicity', 'Ethnicity'), 
                ('Genotypes', 'Genotype'), 
                ('Heights', 'Height'), 
                ('Heights', 'HeightDateCollected'), 
                ('ICDCode', 'ICDCode'), 
                ('Illness', 'IllnessNotes'), 
                ('Illness', 'IllnessEndDate'), 
                ('Illness', 'IllnessInstanceID'), 
                ('Illness', 'IllnessStartDate'), 
                ('Intervention', 'InterventionNotes'), 
                ('Intervention', 'InterventionEndDate'), 
                ('Intervention', 'InterventionStartDate'), 
                ('Interventions', 'InterventionCode'), 
                ('Interventions', 'InterventionName'), 
                ('Interventions', 'InterventionType'), 
                ('Subjects', 'BirthYear'), 
                ('Subjects', 'HostSubjectId'), 
                ('Subjects', 'Nationality'), 
                ('Subjects', 'Sex'), 
                ('SubjectType', 'SubjectType'), 
                ('Weights', 'Weight'), 
                ('Weights', 'WeightDateCollected')] 
    elif file_type == 'specimen':
        headers = [('AdditionalMetaData', 'DaysSinceExperimentStart'), 
                ('AdditionalMetaData', 'ExampleMetaData'), 
                ('AdditionalMetaData', 'SubjectIdCol'), 
                ('Aliquot', 'AliquotID'), 
                ('Aliquot', 'AliquotWeight'), 
                ('Aliquot', 'AliquotWeightUnit'), 
                ('BodySite', 'SpecimenBodySite'), 
                ('BodySite', 'UberonCodeBodySite'), 
                ('CollectionSite', 'Biome'), 
                ('CollectionSite', 'CollectionSiteName'), 
                ('CollectionSite', 'CollectionSiteTechnician'), 
                ('CollectionSite', 'Depth'), 
                ('CollectionSite', 'Elevation'), 
                ('CollectionSite', 'Environment'), 
                ('CollectionSite', 'Latitude'), 
                ('CollectionSite', 'Longitude'), 
                ('CollectionSite', 'Material'), 
                ('Experiment', 'ExperimentName'), 
                ('Lab', 'ContactEmail'), 
                ('Lab', 'ContactName'), 
                ('Lab', 'PrimaryInvestigator'), 
                ('RawData', 'BarcodeSequence'), 
                ('RawData', 'LinkerPrimerSequence'), 
                ('RawData', 'RawDataID'), 
                ('RawData', 'RawDataNotes'), 
                ('RawDataProtocol', 'RawDataDatePerformed'), 
                ('RawDataProtocol', 'RawDataProcessor'), 
                ('RawDataProtocol', 'RawDataProtocolID'), 
                ('RawDataProtocols', 'FinishingStrategyCoverage'), 
                ('RawDataProtocols', 'FinishingStrategyStatus'), 
                ('RawDataProtocols', 'NumberOfContigs'), 
                ('RawDataProtocols', 'Primer'), 
                ('RawDataProtocols', 'RawDataConditions'), 
                ('RawDataProtocols', 'SequencingMethod'), 
                ('RawDataProtocols', 'TargetGene'), 
                ('Results', 'ResultID'), 
                ('Results', 'ResultsLocation'), 
                ('ResultsProtocol', 'ResultsDatePerformed'), 
                ('ResultsProtocol', 'ResultsProcessor'), 
                ('ResultsProtocol', 'ResultsProtocolID'), 
                ('ResultsProtocols', 'ResultsMethod'), 
                ('ResultsProtocols', 'ResultsTool'), 
                ('ResultsProtocols', 'ResultsToolVersion'), 
                ('Sample', 'SampleID'),
                ('Sample', 'SampleWeight'),
                ('Sample', 'SampleWeightUnit'),
                ('SampleProtocol', 'SampleDatePerformed'),
                ('SampleProtocol', 'SampleProcessor'),
                ('SampleProtocol', 'SampleProtocolID'),
                ('SampleProtocol', 'SampleProtocolNotes'),
                ('SampleProtocols', 'SampleConditions'),
                ('SampleProtocols', 'SampleTool'),
                ('SampleProtocols', 'SampleToolVersion'),
                ('Specimen', 'SpecimenCollectionDate'),
                ('Specimen', 'SpecimenCollectionMethod'),
                ('Specimen', 'SpecimenCollectionTime'),
                ('Specimen', 'SpecimenID'),
                ('Specimen', 'SpecimenNotes'),
                ('Specimen', 'SpecimenWeight'),
                ('Specimen', 'SpecimenWeightUnit'),
                ('StorageLocation', 'StorageInstitution'),
                ('StorageLocation', 'StorageFreezer'),
                ('Study', 'RelevantLinks'),
                ('Study', 'StudyName'),
                ('Study', 'StudyType'),
                ('Type', 'SpecimenType'),
                ('Type', 'UberonCodeType')]

    
    # Blank data columns
    headerCount = 3
    diff = len(df)-headerCount

    for header in headers:
        blank_column = df.copy(deep=True)
        blank_column.loc[headerCount:len(df), header] = np.array([''] * diff)
        
        write_test_metadata(blank_column, '{}/blank_column_tests/{}/'.format(file_path, file_type), 'blank_{}.tsv'.format(header[1]))

    # NA data columns
    for header in headers:
        na_column = df.copy(deep=True)
        na_column.loc[headerCount:len(df), header] = np.array(['NA'] * diff)

        write_test_metadata(na_column, '{}/na_column_tests/{}/'.format(file_path, file_type), 'na_{}.tsv'.format(header[1]))

    # Other data columns
    for header in headers:
        other_column = df.copy(deep=True)
        other_column.loc[headerCount:len(df), header] = np.array([{True if randrange(2) == 0 else False : True if randrange(2) == 0 else False} for i in range(diff)])

        write_test_metadata(other_column, '{}/other_column_tests/{}/'.format(file_path, file_type), 'other_{}.tsv'.format(header[1]))

    # Numbers data columns
    for header in headers:
        number_column = df.copy(deep=True)
        number_column.loc[headerCount:len(df), header] = np.array([randrange(2000) for i in range(diff)])

        write_test_metadata(number_column, '{}/number_column_tests/{}/'.format(file_path, file_type), 'number_{}.tsv'.format(header[1]))

    # Dates data columns
    for header in headers:
        date_column = df.copy(deep=True)
        date_column.loc[headerCount:len(df), header] = np.array([dt.date(randrange(2015, 2026), randrange(1, 13), randrange(1, 29)) for i in range(diff)])

        write_test_metadata(date_column, '{}/date_column_tests/{}/'.format(file_path, file_type), 'date_{}.tsv'.format(header[1]))


if __name__ == '__main__':
    main()
