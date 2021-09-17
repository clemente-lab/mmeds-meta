#!python
import gzip
import click
from pathlib import Path

__author__ = 'Adam Cantor'

"""
This script takes in four fastq.gz files, and demultiplexes them based on sample barcode data.
This script is allows MMEDS to run demultiplexing using combinatorial dual barcode indexing.
"""

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-r1', '--reads-forward', required=True, help='Path to .fastq.gz forward read file')
@click.option('-r2', '--reads-reverse', required=True, help='Path to .fastq.gz reverse read file')
@click.option('-i1', '--barcodes-forward', required=True, help='Path to .fastq.gz forward barcodes file')
@click.option('-i2', '--barcodes-reverse', required=True, help='Path to .fastq.gz reverse barcodes file')
def main(reads_forward, reads_reverse, barcodes_forward, barcodes_reverse):
    # Unzip the four required files
    r1 = gzip.open(reads_forward)
    r2 = gzip.open(reads_reverse)
    i1 = gzip.open(barcodes_forward)
    i2 = gzip.open(barcodes_reverse)

    # TODO: Replace with click option file
    tmp_adapters = {
        '240_16': ['CTCGACTT', 'ATCGTACG'],
        '240_1': ['CTCGACTT', 'ACTATCTG'],
        '242_16': ['CTCGACTT', 'TAGCGAGT'],
        '242_1': ['CTCGACTT', 'CTGCGTGT'],
        'BC258': ['CTCGACTT', 'TCATCGAG'],
        'NTC': ['CTCGACTT', 'CGTGAGTG'],
        'HD-7002': ['CTCGACTT', 'GGATATCT'],
        'HD-7003': ['CTCGACTT', 'GACACCGT']
    }

    # Run demux and output all data as fastq.gz files
    output = demux(r1, r2, i1, i2, tmp_adapters)
    out_dir = Path('output_dir/')
    out_dir.mkdir(parents=True, exist_ok=True)
    # All output text exists in 'output'
    for key in output:
        # Creates two output fastq.gz for each sample and populates it
        path1 = out_dir / '{}_L001_R1_001.fastq.gz'.format(key)
        path2 = out_dir / '{}_L001_R2_001.fastq.gz'.format(key)
        path1.touch()
        path2.touch()
        print(output[key][0])
        path1.write_bytes(gzip.compress(output[key][0].encode('utf-8')))
        path2.write_bytes(gzip.compress(output[key][1].encode('utf-8')))

# Demultiplexes the data
def demux(r1, r2, i1, i2, sample_barcodes):
    output = {}
    r1_str, r2_str, i1_str, i2_str = ['', '', '', '']
    debug_count = 0
    for key in sample_barcodes:
        output[key] = ['', '']

    # Run until end of file, all files must be the same length else error
    while True:
        debug_count += 1
        print(debug_count)

        # Grab four lines from each file
        r1_str = get_lines(r1, 4)
        r2_str = get_lines(r2, 4)
        i1_str = get_lines(i1, 4).split('\n')
        i2_str = get_lines(i2, 4).split('\n')

        # End when we get to EOF
        if len(i1_str) < 4:
            break
        for key in sample_barcodes:
            # When sample barcodes match file barcodes, add those reads to output
            if i1_str[1] == sample_barcodes[key][0] and i2_str[1] == sample_barcodes[key][1]:
                output[key][0] += r1_str
                output[key][1] += r2_str
    return output

# Helper to grab multiple lines
def get_lines(f, num):
    ret = ''
    for i in range(num):
        ret += f.readline().decode('utf-8')
    return ret


if __name__ == '__main__':
    main()
