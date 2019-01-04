from pathlib import Path
from nbformat import v4
from collections import defaultdict
from subprocess import run

import nbformat as nbf
import os
from mmeds.config import STORAGE_DIR
from mmeds.mmeds import log


def summarize_qiime1(metadata=['Ethnicity', 'Nationality'], files={}, execute=False, name='analysis', run_path='/home/david/Work/data-mmeds/summary'):
    """
    Create the summary PDF for qiime1 analysis
    """
    log('Start summary notebook')
    original_path = Path.cwd()
    os.chdir(run_path)
    # Load the code templates
    with open(STORAGE_DIR / 'summary_code.txt') as f:
        data = f.read().split('\n=====\n')

    # Dict for storing all the different code templates
    source = {}
    for code in data:
        parts = code.split('<source>\n')
        source[parts[0]] = parts[1]

    def taxa_plots(path, data_file):
        """ Create plots for taxa summary files. """
        cells = []
        for column in metadata:
            filename = '{}-{}.png'.format(data_file.split('.')[0], column)
            cells.append(v4.new_markdown_cell(source='## View {f} grouped by {group}'.format(f=data_file, group=column)))
            cells.append(v4.new_code_cell(source=source['taxa_py_qiime1'].format(file1=data_file, group=column)))
            cells.append(v4.new_code_cell(source=source['taxa_r'].format(plot=filename, group=column)))
            cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
        return cells

    def alpha_plots(path, data_file):
        """ Create plots for alpha diversity files. """
        filename = data_file.split('.')[0] + '.png'
        cells = []
        cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=data_file)))
        cells.append(v4.new_code_cell(source=source['alpha_py_qiime1'].format(file1=data_file)))
        cells.append(v4.new_code_cell(source=source['alpha_r'].format(file1=filename, xaxis='SequencesPerSample')))
        cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
        return cells

    def beta_plots(path, data_file):
        """ Create plots for alpha diversity files. """
        cells = []
        for column in metadata:
            filename = '{}-{}.png'.format(data_file.split('.')[0], column)
            cells.append(v4.new_markdown_cell(source='## View {f} grouped by {group}'.format(f=data_file, group=column)))
            cells.append(v4.new_code_cell(source=source['beta_py'].format(file1=data_file, group=column)))
            cells.append(v4.new_code_cell(source=source['beta_r'].format(file1=filename)))
            cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
        return cells

    def summarize(path, files, execute, no_files=False):
        """ Create the python notebook containing the summary of analysis results. """
        # Get the files to summarize from the index
        if no_files:
            files = defaultdict(list)
            with open(path.parent / 'file_index.tsv') as f:
                lines = f.readlines()
            for line in lines:
                parts = line.strip('\n').split('\t')
                files[parts[0]].append(parts[1])

        # Create the list to store all cells
        cells = []

        with open(path / 'biom_table_summary.txt') as f:
            output = f.read().replace('\n', '  \n').replace('\r', '  \r')

        # Add all the cells containing the different files
        cells.append(v4.new_markdown_cell(source='# Notebook Setup'))
        cells.append(v4.new_code_cell(source=source['py_setup']))
        cells.append(v4.new_code_cell(source=source['r_setup']))
        cells.append(v4.new_markdown_cell(source='# OTU Summary'))
        cells.append(v4.new_markdown_cell(source=output))
        cells.append(v4.new_markdown_cell(source='To view the full otu table, execute the code cell below'))
        cells.append(v4.new_code_cell(source=source['otu_py']))
        cells.append(v4.new_markdown_cell(source='# Taxa Summary'))
        for data_file in files['taxa']:
            cells += taxa_plots(path, data_file)
        cells.append(v4.new_markdown_cell(source='# Diversity Plot Legend'))
        cells.append(v4.new_code_cell(source=source['legend_py'].format()))
        cells.append(v4.new_code_cell(source=source['legend_r'].format(plot='legend.png')))
        cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot='legend.png')))
        cells.append(v4.new_markdown_cell(source='# Alpha Diversity Summary'))
        for data_file in files['alpha']:
            cells += alpha_plots(path, data_file)
        cells.append(v4.new_markdown_cell(source='# Beta Diversity Summary'))
        for data_file in sorted(files['beta']):
            if 'dm' in data_file:
                cells.append(v4.new_markdown_cell(source="## View {file1}".format(file1=data_file)))
                cells.append(v4.new_code_cell(source="df = read_csv('{file1}', sep='\t')".format(file1=data_file)))
            else:
                cells += beta_plots(path, data_file)

        # Hide the code in all cells
        for cell in cells:
            cell.metadata['hide_code'] = True
            cell.metadata['hide_input'] = True
        nn = nbf.v4.new_notebook(cells=cells)
        meta = {
            'metadata': {
                'authors': [{'name': 'David Wallach', 'email': 'david.wallach@mssm.edu'}],
                'name': 'MMEDS Analysis Summary',
                'title': 'MMEDS Analysis Summary',
                'path': '{path}/'.format(path=path)
            }
        }
        nn.update(meta)
        return nn

    def write_notebook(nn):
        nbf.write(nn, str(path / '{}.ipynb'.format(name)))

        cmd = 'jupyter nbconvert --template=nbextensions --to=latex {}.ipynb'.format(name)
        if execute:
            cmd += ' --execute'
        run(cmd, shell=True, check=True)

        # Add the line missing from the template
        cmd = r"sed -i '1i\\\documentclass[]{{article}}' {}.tex".format(name)
        run(cmd, shell=True, check=True)

        # Convert to pdf
        cmd = 'pdflatex {name}.tex {name}.pdf'.format(name=name)
        run(cmd, shell=True, check=True)

    path = Path(run_path)

    nn = summarize(path, files, execute)
    write_notebook(nn)
    os.chdir(original_path)
