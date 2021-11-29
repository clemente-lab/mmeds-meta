import click
from pathlib import Path
from mmeds.util import join_taxa_with_correlations, generate_variable_abundance
import pandas as pd

__author__ = "Adam Cantor"
__copyright__ = "Copyright 2021 Clemente Lab"
__credits__ = ["Adam Cantor", "Jose Clemente"]
__license__ = "GPL"

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--i-feature-table', required=True,
              help='A feature-table.biom converted to a .tsv')  # Maybe the .qza instead?
@click.option('-c', '--i-correlation-files', required=True, multiple=True,
              help='The correlation files outputted by the qiime1 script observed_metadata_correlation.py')
@click.option('-t', '--i-taxonomy', required=True, help='Taxonomy tsv extracted form taxonomy.qza')
@click.option('-m', '--m-mapping-file', required=True, help='A qiime mapping file')
@click.option('-d', '--o-directory', required=False, default='.',
              help='Directory to output files to, default working directory')
@click.option('-o', '--o-significant-abundance', required=True, help='Output tsv file')
def generate_significant_abundance(
    i_feature_table,
    i_correlation_files,
    i_taxonomy,
    m_mapping_file,
    o_directory,
    o_significant_abundance
):
    feature_table = Path(i_feature_table)
    taxonomy = Path(i_taxonomy)
    mapping_file = Path(m_mapping_file)
    correlation_files = [Path(f) for f in i_correlation_files]

    out_dir = Path(o_directory)
    out_file = Path(o_significant_abundance)

    correlation_taxa_files = join_taxa_with_correlations(taxonomy, correlation_files, out_dir)
    df = generate_variable_abundance(feature_table, mapping_file, correlation_taxa_files)
    df.to_csv(out_file, sep='\t')


if __name__ == '__main__':
    generate_significant_abundance()
