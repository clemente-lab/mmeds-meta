from pathlib import Path
from nbformat import v4
from collections import defaultdict

import nbformat as nbf
from nbconvert import PDFExporter
from nbconvert.preprocessors import ExecutePreprocessor
from mmeds.config import STORAGE_DIR


def run(execute, name='analysis', run_path='/home/david/Work/data-mmeds/summary'):
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
        filename = data_file.split('.')[0] + '.png'
        cells = []
        cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=data_file)))
        cells.append(v4.new_code_cell(source=source['taxa_py'].format(file1=data_file)))
        cells.append(v4.new_code_cell(source=source['taxa_r'].format(plot=filename)))
        cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
        return cells

    def alpha_plots(path, data_file):
        """ Create plots for alpha diversity files. """
        filename = data_file.split('.')[0] + '.png'
        cells = []
        cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=data_file)))
        cells.append(v4.new_code_cell(source=source['alpha_py'].format(file1=data_file)))
        cells.append(v4.new_code_cell(source=source['alpha_r'].format(file1=filename)))
        cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
        return cells

    def beta_plots(path, data_file):
        """ Create plots for alpha diversity files. """
        filename = data_file.split('.')[0] + '.png'
        cells = []
        cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=data_file)))
        cells.append(v4.new_code_cell(source=source['beta_py'].format(file1=data_file)))
        cells.append(v4.new_code_cell(source=source['beta_r'].format(file1=filename)))
        cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
        return cells

    def summerize(path, execute):
        """ Create the python notebook containing the summary of analysis results. """
        # Get the files to summarize from the index
        files = defaultdict(list)
        with open(path / 'file_index.tsv') as f:
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
        cells.append(v4.new_markdown_cell(source='# Taxa Diversity Summary'))
        for data_file in files['taxa']:
            cells += taxa_plots(path, data_file)
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

        nn = nbf.v4.new_notebook(cells=cells)
        meta = {
            'metadata': {
                'authors': [{'name': 'David Wallach', 'email': 'david.wallach@mssm.edu'}],
                'name': 'MMEDS Analysis Summary',
                'title': 'MMEDS Analysis Summary'
            }
        }
        nn.update(meta)

        return nn

    def write_notebook(nn):
        nbf.write(nn, str(path / '{}.ipynb'.format(name)))

        exp = PDFExporter()
        if execute:
            ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
            ep.preprocess(nn, {'metadata': {'path': '{path}/'.format(path=path)}})

        (pdf_data, resources) = exp.from_notebook_node(nn)
        with open(path / 'notebook.pdf', 'wb') as f:
            f.write(pdf_data)

    path = Path(run_path)

    nn = summerize(path, execute)
    write_notebook(nn)
