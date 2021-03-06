import pandas as pd
import click

from collections import defaultdict
from mmeds.util import write_metadata, camel_case

mapping = {
    'brian.Type': ('Type', 'SpecimenType'),
    'gender.factor': ('Subjects', 'Sex'),
    'curr_height': ('Heights', 'Height'),
    'curr_weight': ('Weights', 'Weight'),
    'race.factor': ('Ethnicity', 'Ethnicity'),
    'Samples': ('RawData', 'RawDataID'),
    'description': ('AdditionalMetaData', 'MeconiumDescription')

}

# Ratio of original value to new value
conversions = {
    'curr_height': 0.0254,
    'curr_weight': 0.4536
}
__author__ = "David Wallach"
__copyright__ = "Copyright 2019, The Clemente Lab"
__credits__ = ["David Wallach", "Jose Clemente"]
__license__ = "GPL"
__maintainer__ = "David Wallach"
__email__ = "d.s.t.wallach@gmail.com"

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--input_file',
              type=click.Path(exists=True),
              help='Path to Meconium metadata file')
@click.option('-o', '--output_file',
              type=click.Path(exists=False),
              help='Path to write mmeds metadata file to')
def convert(input_file, output_file):

    mmeds = defaultdict(list)

    if 'xlsx' in input_file:
        idf = pd.read_excel(input_file)
    else:
        idf = pd.read_csv(input_file, sep='\t')

    fdf = pd.read_csv('inF.TXT', sep=' ')
    rdf = pd.read_csv('inR.TXT', sep=' ')

    fdf.set_index('index', inplace=True)
    rdf.set_index('index', inplace=True)

    # Get the values for LinkerPrimer and BarcodeSequence
    for i in range(len(idf)):
        fcode = idf['brian.Fcode'].iloc[i]
        rcode = idf['brian.Rcode'].iloc[i]
        mmeds[('RawData', 'BarcodeSequence')].append(fdf.loc[fcode].barcode + rdf.loc[rcode].barcode)
        mmeds[('RawData', 'LinkerPrimerSequence')].append(fdf.loc[fcode].Sequence + rdf.loc[rcode].Sequence)

    # Add all mapped columns to the dictionary
    for col in idf.columns:
        try:
            mmeds_col = mapping[col]
        except KeyError:
            mmeds_col = ('AdditionalMetaData', camel_case(col))

        try:
            ratio = conversions[col]
        except KeyError:
            ratio = 1

        if not ratio == 1:
            for item in idf[col].tolist():
                try:
                    mmeds[mmeds_col].append(ratio * item)
                except TypeError:
                    num = float(item.split(' ')[0])
                    mmeds[mmeds_col].append(ratio * num)
        else:
            mmeds[mmeds_col] = idf[col].tolist()
    print('KEYESSSS')
    print(mmeds.keys())

    write_metadata(mmeds, output_file)


if __name__ == "__main__":
    convert()
