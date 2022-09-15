import click
from mmeds.util import format_table_to_lefse

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--i-table', required=True,
              help='TSV extracted from a Qiime2 FeatureTable')
@click.option('-m', '--metadata-file', required=True,
              help='Qiime2 formatted mapping file')
@click.option('-c', '--metadata-column-class', required=True,
              help='Main metadata column on which to perform LEfSe analyis')
@click.option('-s', '--metadata-column-subclass', required=False,
              help='Subclass on which to perform LEfSe analysis')
@click.option('-u', '--metadata-column-subject', required=False,
              help='If provided, column values will replace the given SampleIDs')
@click.option('-o', '--o-table', required=True,
              help='Output TSV ready for LEfSe\'s "format_input.py"')
def format_table(i_table, metadata_file, metadata_column_class, metadata_column_subclass,
                 metadata_column_subject, o_table):
    """ Script that calls the format function in util.py to convert to a format that can be read by format_input.py """
    format_table_to_lefse(i_table, metadata_file, metadata_column_class, metadata_column_subclass,
                          metadata_column_subject, o_table)


if __name__ == '__main__':
    format_table()
