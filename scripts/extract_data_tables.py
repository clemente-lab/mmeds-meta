#!/usr/bin/env python3

import click
import subprocess as sp
from yaml import safe_load
from pathlib import Path

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('-i', '--i-config', required=True,
              help='MMEDS analysis configuration yaml file')
@click.option('-p', '--p-path-to-tables', required=True,
              help='The analysis directory which contains the data tables')
def extract_tables(i_config, p_path_to_tables):
    """ Script that calls the format function in util.py to convert to a format that can be read by format_input.py """
    i_config = Path(i_config).resolve()
    tables_path = Path(p_path_to_tables).resolve()
    tmp_dir = tables_path / "tmp_unzip"
    with open(i_config, "r") as f:
        config = safe_load(f)

    for table in config['tables']:
        qza_file = tables_path / f"{table}.qza"
        tsv_file = tables_path / f"{table}.tsv"

        if not qza_file.exists():
            raise FileNotFoundError(f"No data file named {qza_file.name} exists at {tables_path}")

        sp.run(["unzip", "-jo", str(qza_file), "-d", str(tmp_dir)])
        sp.run(["biom", "convert", "--to-tsv", "-i", str(tmp_dir / "feature-table.biom"), "-o", str(tsv_file)])
        sp.run(["rm", "-rf", str(tmp_dir)])
        sp.run(["sed", "-i", "1d;2s/^#//", str(tsv_file)])


if __name__ == '__main__':
    extract_tables()
