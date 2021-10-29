import click
import pandas as pd
from pathlib import Path
from mmeds.util import make_grouped_mapping_file

__author__ = "Adam Cantor"
__copyright__ = "Copyright 2021, The Clemente Lab"
__credits__ = ["Adam Cantor", "Jose Clemente"]
__license__ = "GPL"

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-m', '--m-metadata-file', required=True, help='Path to full mapping file tsv')
@click.option('-c', '--m-metadata-column', required=True, help='Category around which to group samples')
@click.option('-o', '--o-grouped-metadata-file', required=True, help='Path to output grouped metadata file')
def make_file(m_metadata_file, m_metadata_column, o_grouped_metadata_file):
    """
    Script that takes in a qiime mapping file and one of its headers, and outputs
    another mapping file that has one column, containing the unique values of the
    column of the original file
    """

    out_s = make_grouped_mapping_file(m_metadata_file, m_metadata_column)

    # Write output to file
    p_out = Path(o_grouped_metadata_file)
    p_out.touch()
    p_out.write_text(out_s)


if __name__ == '__main__':
    make_file()
