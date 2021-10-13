import click
import pandas as pd
from pathlib import Path
from mmeds.util import make_pheniqs_config

__author__ = "Adam Cantor"
__copyright__ = "Copyright 2021, The Clemente Lab"
__credits__ = ["Adam Cantor", "Jose Clemente"]
__license__ = "GPL"

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-r1', '--reads-forward', required=True, help='Path to forward reads fastq.gz')
@click.option('-r2', '--reads-reverse', required=True, help='Path to reverse reads fastq.gz')
@click.option('-i1', '--barcodes-forward', required=True, help='Path to forward barcodes fastq.gz')
@click.option('-i2', '--barcodes-reverse', required=True, help='Path to reverse barcodes fastq.gz')
@click.option('-m', '--mapping-file', required=True, help='Path to mapping file tsv')
@click.option('-o', '--o-config', required=True, help='Path to output config file json')
@click.option('-d', '--o-directory', required=True, help='Directory for demultiplexed files to be written to')
def make_file(reads_forward, reads_reverse, barcodes_forward, barcodes_reverse, mapping_file, o_config, o_directory):
    """
    Method for taking in fastq.gz files and tsv mapping files and creating an
    output.json file that can be read by the 'pheniqs' module for demultiplexing
    """

    out_s = make_pheniqs_config(reads_forward, reads_reverse,
            barcodes_forward, barcodes_reverse, mapping_file, o_directory)

    # Write output.json to file
    p_out = Path(o_config)
    p_out.touch()
    p_out.write_text(out_s)


if __name__ == '__main__':
    make_file()
