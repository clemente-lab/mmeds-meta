from pathlib import Path
from nbformat import v4
from collections import defaultdict
from subprocess import run
from itertools import combinations

import nbformat as nbf
import os
from mmeds.config import STORAGE_DIR
from mmeds.mmeds import log


def summarize(metadata=['Ethnicity', 'Nationality'],
              analysis_type='qiime1',
              files={},
              execute=False,
              name='analysis',
              run_path='/home/david/Work/data-mmeds/summary'):
    """
    Create the summary PDF for qiime1 analysis
    ==========================================
    :metadata: A list of strings. Includes the names of metadata columns to include in the analysis.
    :files: A dictionary of locations for the files to use when creating plots.
    :execute: A boolean. If True execute the notebook when exporting to PDF, otherwise don't.
    :name: A string. The name of the notebook and PDF document.
    :run_path: A file path. The path to the directory containing all the summary files.
    """

    def taxa_plots(data_file):
        """
        Create plots for taxa summary files.
        ====================================
        :data_file: The location of the file to create the plotting code for.
        """
        cells = []
        for column in metadata:
            filename = '{}-{}.png'.format(data_file.split('.')[0], column)
            cells.append(v4.new_markdown_cell(source='## {f} grouped by {group}'.format(f=data_file,
                                                                                        group=column)))
            cells.append(v4.new_code_cell(source=source['taxa_py_{}'.format(analysis_type)].format(file1=data_file,
                                                                                                   group=column)))
            cells.append(v4.new_code_cell(source=source['taxa_r'].format(plot=filename,
                                                                         group=column)))
            cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
        return cells

    def alpha_plots(data_file):
        """
        Create plots for alpha diversity files.
        =======================================
        :data_file: The location of the file to create the plotting code for.
        """
        if analysis_type == 'qiime1':
            xaxis = 'SequencesPerSample'
        elif analysis_type == 'qiime2':
            xaxis = 'SamplingDepth'
        filename = data_file.split('.')[0] + '.png'
        cells = []
        cells.append(v4.new_markdown_cell(source='## {f}'.format(f=data_file)))
        cells.append(v4.new_code_cell(source=source['alpha_py_{}'.format(analysis_type)].format(file1=data_file)))
        cells.append(v4.new_code_cell(source=source['alpha_r'].format(file1=filename, xaxis=xaxis)))
        cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
        cells.append(v4.new_code_cell(source='Image("legend.png")'))
        return cells

    def beta_plots(data_file):
        """
        Create plots for alpha diversity files.
        =======================================
        :data_file: The location of the file to create the plotting code for.
        """
        cells = []
        for column in metadata:
            plot = '{}-{}.png'.format(data_file.split('.')[0], column)
            subplot = '{}-%s-%s.png'.format(plot.split('.')[0])
            cells.append(v4.new_markdown_cell(source='## {f} grouped by {group}'.format(f=data_file,
                                                                                        group=column)))
            cells.append(v4.new_code_cell(source=source['beta_py'].format(file1=data_file,
                                                                          group=column)))
            cells.append(v4.new_code_cell(source=source['beta_r'].format(plot=plot,
                                                                         subplot=subplot,
                                                                         cat=column)))
            cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=plot)))
            cells.append(v4.new_code_cell(source='Image("legend.png")'))
            for x, y in combinations(['PC1', 'PC2', 'PC3'], 2):
                cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=subplot % (x, y))))

        return cells

    def summarize(path, files, execute, no_files=False):
        """
        Create the python notebook containing the summary of analysis results.
        =====================================================================
        :path: A file path. The path to the directory containing the files to plot
        :files: A dictionary of locations for the files to use when creating plots.
        :execute: A boolean. If True execute the notebook when exporting to PDF, otherwise don't.
        :no_files: A boolean. If True use a local file_index.tsv file to populate the files dict.
        """
        # Get the files to summarize from the index
        if no_files:
            files = defaultdict(list)
            with open(path.parent / 'file_index.tsv') as f:
                lines = f.readlines()
            for line in lines:
                parts = line.strip('\n').split('\t')
                files[parts[0]].append(parts[1])

        # Used to store the notebook cells
        cells = []

        # Add cells for setting up the R and Python environments
        cells.append(v4.new_code_cell(source=source['py_setup']))
        cells.append(v4.new_code_cell(source=source['r_setup']))

        # Add the cells for the OTU summary
        if analysis_type == 'qiime1':
            with open(path / 'biom_table_summary.txt') as f:
                output = f.read().replace('\n', '  \n').replace('\r', '  \r')
            cells.append(v4.new_markdown_cell(source='# OTU Summary'))
            cells.append(v4.new_markdown_cell(source=output))
            cells.append(v4.new_markdown_cell(source='To view the full otu table, execute the code cell below'))
            cells.append(v4.new_code_cell(source=source['otu_py']))

        # Add the cells for the Taxa summaries
        cells.append(v4.new_markdown_cell(source='# Taxa Summary'))
        for data_file in sorted(files['taxa']):
            cells += taxa_plots(data_file)
        cells.append(v4.new_markdown_cell(source='# Diversity Plot Legend'))
        cells.append(v4.new_code_cell(source=source['legend_py'].format(fontfile=STORAGE_DIR / 'ABeeZee-Regular.otf',
                                                                        fontsize=15,
                                                                        legend='legend.png')))
        cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot='legend.png')))

        # Add the cells for Alpha Diversity
        cells.append(v4.new_markdown_cell(source='# Alpha Diversity Summary'))
        for data_file in files['alpha']:
            cells += alpha_plots(data_file)

        # Add the cells for Beta Diversity
        cells.append(v4.new_markdown_cell(source='# Beta Diversity Summary'))
        for data_file in sorted(files['beta']):
            if 'dm' in data_file:
                cells.append(v4.new_markdown_cell(source="## {file1}".format(file1=data_file)))
                cells.append(v4.new_code_cell(source="df = read_csv('{file1}', sep='\t')".format(file1=data_file)))
            else:
                cells += beta_plots(data_file)

        # Create the notebook and
        meta = {
            'latex_metadata': {
                'author': 'Clemente Lab',
                'affiliation': 'Icahn School of Medicine at Mount Sinai',
                'name': 'MMEDS Analysis Summary',
                'title': 'MMEDS Analysis Summary'
            },
            'hide_input': True
        }
        nn = nbf.v4.new_notebook(cells=cells, metadata=meta)
        return nn

    def write_notebook(nn):
        """
        Write the notebook and export it to a PDF.
        ==========================================
        :nn: A python notebook object.
        """
        nbf.write(nn, str(path / '{}.ipynb'.format(name)))
        cmd = 'jupyter nbconvert --template={}/revtex.tplx --to=latex {}.ipynb'.format(STORAGE_DIR, name)
        if execute:
            cmd += ' --execute'
        run(cmd, shell=True, check=True)

        # Add the line missing from the template
        cmd = r"sed -i '1i\\\documentclass[]{{article}}' {}.tex".format(name)
        run(cmd, shell=True, check=True)

        # Convert to pdf
        cmd = 'pdflatex {name}.tex {name}.pdf'.format(name=name)
        run(cmd, shell=True, check=True)

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

    path = Path(run_path)

    nn = summarize(path, files, execute)
    write_notebook(nn)

    # Switch back to the original directory
    os.chdir(original_path)
