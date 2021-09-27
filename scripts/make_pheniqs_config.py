import click
import pandas as pd
from pathlib import Path

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
    # The top of the output.json file, including R1, I1, I2, and R2
    out_s = '{\n\t"input": [\n\t\t"%s",\n\t\t"%s",\n\t\t"%s",\n\t\t"%s"\n\t],\n\t"output": [ "output_all.fastq" ],'
    out_s += '\n\t"template": {\n\t\t"transform": {\n\t\t\t"comment": "This global transform directive specifies the \
    segments that will be written to output as the biological sequences of interest, this represents all of R1 and R2."'
    out_s += ',\n\t\t\t"token": [ "0::", "3::" ]\n\t\t}\n\t},\n\t"sample": {\n\t\t"transform": {\n\t\t\t"token": '
    out_s += '[ "1::8", "2::8" ]\n\t\t},\n\t\t"algorithm": "pamld",\n\t\t"confidence threshold": 0.95,\n\t\t'
    out_s += '"noise": 0.05,\n\t\t"codec": {\n'

    out_s = out_s % (reads_forward, barcodes_forward, barcodes_reverse, reads_reverse)

    # Template for each sample and their barcodes
    sample_template = '\t\t\t"@%s": {\n\t\t\t\t"LB": "%s",\n\t\t\t\t"barcode": [ "%s", "%s" ],\n\t\t\t\t"output": [\
        \n\t\t\t\t\t"%s/%s_S1_L001_R1_001.fastq.gz",\n\t\t\t\t\t"%s/%s_S1_L001_R2_001.fastq.gz"\n\t\t\t\t]\n\t\t\t}'

    # Getting mapping file as DataFrame
    map_df = pd.read_csv(Path(mapping_file), sep='\t', header=[0, 1], na_filter=False)

    # Adding each sample and barcodes to output.json
    length = len(map_df['#SampleID']['#q2:types'])
    for i in range(length):
        name = map_df['#SampleID']['#q2:types'][i]
        b1 = map_df['BarcodeSequence']['categorical'][i]
        b2 = map_df['BarcodeSequenceR']['categorical'][i]
        out_s += sample_template % (name, name, b1, b2, o_directory, name, o_directory, name)
        if i == length-1:
            out_s += '\n'
        else:
            out_s += ',\n'

    # Bottom of output.json file
    out_s += '\t\t},\n\t\t"undetermined": {\n\t\t\t"output": [\n\t\t\t\t\
        "%s/undetermined_S1_L001_R1_001.fastq.gz",\n\t\t\t\t\
        "%s/undetermined_S1_L001_R2_001.fastq.gz"\n\t\t\t]\n\t\t}\n\t}\n}' % (o_directory, o_directory)

    # Write output.json to file
    p_out = Path(o_config)
    p_out.touch()
    p_out.write_text(out_s)


if __name__ == '__main__':
    make_file()
