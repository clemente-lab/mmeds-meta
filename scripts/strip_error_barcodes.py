import click
import os
import gzip
import pandas as pd
from pathlib import Path

__author__ = "Adam Cantor"
__copyright__ = "Copyright 2021 Clemente Lab"
__credits__ = ["Adam Cantor", "Jose Clemente"]
__license__ = "GPL"

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-n', '--num-allowed-errors', default=1, type=int,
              help='The number of allowed barcode errors, barcodes with more errors than this will be removed.')
@click.option('-m', '--mapping-file', required=True, help='Path to the mapping file')
@click.option('-i', '--input-dir', required=True, help='Directory with fastq.gz files')
@click.option('-o', '--output-dir', required=True, help='Directory to output new fastq.gz files to')
def strip_errors(num_allowed_errors, mapping_file, input_dir, output_dir):
    """
    Method to strip reads from individual demultiplexed fastq.gz files if a read has
    barcode error greater than N (num_allowed_errors) and write to output
    """

    # Get mapping file as DataFrame and save sample data to hash
    map_df = pd.read_csv(Path(mapping_file), sep='\t', header=[0], na_filter=False)
    map_hash = {}

    for i in range(len(map_df['#SampleID'])):
        if i > 0:
            map_hash[map_df['#SampleID'][i]] = \
                    (
                            map_df['BarcodeSequence'][i],
                            map_df['BarcodeSequenceR'][i]
                    )
    # Strip errors for each fastq.gz file in input_dir
    count = 1
    for filename in os.listdir(input_dir):
        sample = ''
        # Match sample file to sample in hash
        for key in map_hash:
            if filename.startswith(key):
                sample = key
                break
        if not sample == '':
            # Open sample file for reading
            f = gzip.open(Path(input_dir) / filename, mode='rt')
            out = ''

            line = f.readline()
            # Compare each line's barcodes with the expected barcodes and count diff
            while line is not None and not line == '':
                code = line[len(line)-18:len(line)-1].split('-')
                diff = 0
                for i in range(len(code[0])):
                    if not code[0][i] == map_hash[sample][0][i]:
                        diff += 1

                for i in range(len(code[1])):
                    if not code[1][i] == map_hash[sample][1][i]:
                        diff += 1

                # If diff does not exceed N, write read to output
                if diff <= num_allowed_errors:
                    out += line
                    out += f.readline()
                    out += f.readline()
                    out += f.readline()
                # Else skip read
                else:
                    f.readline()
                    f.readline()
                    f.readline()

                line = f.readline()
            # Write output file to output_dir
            p_out = Path(output_dir) / filename
            p_out.touch()
            p_out.write_bytes(gzip.compress(out.encode('utf-8')))
            print(count, 'written', filename)
            count += 1


if __name__ == '__main__':
    strip_errors()
