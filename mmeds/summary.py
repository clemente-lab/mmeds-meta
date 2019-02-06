from pathlib import Path
from nbformat import v4
from collections import defaultdict
from subprocess import run
from itertools import combinations
from shutil import copy, rmtree, make_archive

import nbformat as nbf
import os
from mmeds.config import STORAGE_DIR
from mmeds.mmeds import log, load_config


def summarize_qiime(summary_path, load_info, config_file, tool):
    """ Handle setup and running the summary for the two qiimes """
    path = Path(summary_path)

    # Load the files
    files = {}
    lines = (path / 'file_index.tsv').read_text().strip().split('\n')
    for line in lines:
        parts = line.split('\t')
        files[parts[0]] = Path(parts[1])

    # Load the configuration
    config = load_config(Path(config_file).read_text(), files['metadata'])

    # Create the summary directory
    if not files['summary'].is_dir():
        files['summary'].mkdir()

    if tool == 'qiime1':
        summarize_qiime1(path, files, config, load_info)
    elif tool == 'qiime2':
        summarize_qiime2(path, files, config, load_info)


def summarize_qiime1(path, files, config, load_info):
    """
    Create summary of analysis results
    """
    log('Run summarize')
    diversity = files['diversity_output']
    summary_files = defaultdict(list)

    # Convert and store the otu table
    # Set the environment
    environ = {'SHELL': '/usr/bin/env bash'}
    environ.update(os.environ)
    cmd = '{} biom convert -i {} -o {} --to-tsv --header-key="taxonomy"'
    cmd = cmd.format(load_info,
                     files['otu_output'] / 'otu_table.biom',
                     path / 'otu_table.tsv')
    log(cmd)
    run(cmd, shell=True, check=True, env=environ)

    # Add the text OTU table to the summary
    copy(path / 'otu_table.tsv', files['summary'])
    summary_files['otu'].append('otu_table.tsv')

    def move_files(path, catagory):
        """ Collect the contents of all files match the regex in path """
        data_files = diversity.glob(path.format(depth=config['sampling_depth']))
        for data in data_files:
            copy(data, files['summary'])
            summary_files[catagory].append(data.name)

    move_files('biom_table_summary.txt', 'otu')                       # Biom summary
    move_files('arare_max{depth}/alpha_div_collated/*.txt', 'alpha')  # Alpha div
    move_files('bdiv_even{depth}/*.txt', 'beta')                      # Beta div
    move_files('taxa_plots/*.txt', 'taxa')                            # Taxa summary

    # Get the mapping file
    copy(files['mapping'], path / 'summary/.')

    # Get the template
    copy(STORAGE_DIR / 'revtex.tplx', files['summary'])
    log('Summary path')
    log(path / 'summary')
    mnb = MMEDSNotebook(config=config,
                        analysis_type='qiime1',
                        files=summary_files,
                        execute=True,
                        name='analysis',
                        run_path=path / 'summary')
    mnb.create_notebook()

    log('Make archive')
    result = make_archive(path / 'summary',
                          format='zip',
                          root_dir=path,
                          base_dir='summary')
    log(result)
    log('Summary completed successfully')
    return path / 'summary/analysis.pdf'


def summarize_qiime2(path, files, config, loadinfo):
    """ Create summary of the files produced by the qiime2 analysis. """
    log('Start Qiime2 summary')

    # Setup the summary directory
    summary_files = defaultdict(list)

    # Get Taxa
    cmd = '{} qiime tools export {} --output-dir {}'.format(loadinfo,
                                                            files['taxa_bar_plot'],
                                                            path / 'temp')
    run(cmd, shell=True, check=True)
    taxa_files = (path / 'temp').glob('level*.csv')
    for taxa_file in taxa_files:
        copy(taxa_file, files['summary'])
        summary_files['taxa'].append(taxa_file.name)
    rmtree(path / 'temp')

    # Get Beta
    beta_files = files['core_metrics_results'].glob('*pcoa*')
    for beta_file in beta_files:
        cmd = '{} qiime tools export {} --output-dir {}'.format(loadinfo,
                                                                beta_file,
                                                                path / 'temp')
        run(cmd, shell=True, check=True)
        dest_file = files['summary'] / (beta_file.name.split('.')[0] + '.txt')
        copy(path / 'temp' / 'ordination.txt', dest_file)
        log(dest_file)
        summary_files['beta'].append(dest_file.name)
    rmtree(path / 'temp')

    # Get Alpha
    for metric in ['shannon', 'faith_pd', 'observed_otus']:
        cmd = '{} qiime tools export {} --output-dir {}'.format(loadinfo,
                                                                files['alpha_rarefaction'],
                                                                path / 'temp')
        run(cmd, shell=True, check=True)

        metric_file = path / 'temp/{}.csv'.format(metric)
        copy(metric_file, files['summary'])
        summary_files['alpha'].append(metric_file.name)
    rmtree(path / 'temp')

    # Get the mapping file
    copy(files['mapping'], files['summary'])
    # Get the template
    copy(STORAGE_DIR / 'revtex.tplx', files['summary'])

    # Create the summary
    mnb = MMEDSNotebook(config=config,
                        analysis_type='qiime2',
                        files=summary_files,
                        execute=True,
                        name='analysis',
                        run_path=path / 'summary')

    mnb.create_notebook()
    # Create a zip of the summary
    result = make_archive(path / 'summary',
                          format='zip',
                          root_dir=path,
                          base_dir='summary')
    log('Create archive of summary')
    log(result)

    log('Summary completed succesfully')
    return path / 'summary/analysis.pdf'


class MMEDSNotebook():
    """ A class for handling the creation and execution of the summary notebooks. """

    def __init__(self, config, analysis_type, files, execute, name, run_path):

        """
        Create the summary PDF for qiime1 analysis
        ==========================================
        :config: A dictionary containing all the configuration options for this analysis
        :files: A dictionary of locations for the files to use when creating plots.
        :execute: A boolean. If True execute the notebook when exporting to PDF, otherwise don't.
        :name: A string. The name of the notebook and PDF document.
        :run_path: A file path. The path to the directory containing all the summary files.
        """
        self.cells = []
        self.analysis_type = analysis_type
        self.files = files
        self.execute = execute
        self.name = name
        self.run_path = run_path
        self.config = config

        # Load the code templates
        with open(STORAGE_DIR / 'summary_code.txt') as f:
            data = f.read().split('\n=====\n')

        # Dict for storing all the different code templates
        self.source = {}
        for code in data:
            parts = code.split('<source>\n')
            self.source[parts[0]] = parts[1]

    def add_code(self, text):
        """ Add a code cell to the notebook's list of cells. """
        self.cells.append(v4.new_code_cell(source=text))

    def add_markdown(self, text):
        """ Add a code cell to the notebook's list of cells. """
        self.cells.append(v4.new_markdown_cell(source=text))

    def taxa_plots(self, data_file):
        """
        Create plots for taxa summary files.
        ====================================
        :data_file: The location of the file to create the plotting code for.
        """
        level = data_file.split('.')[0][-1]
        self.add_markdown('## OTU level {level}'.format(level=level))
        for i, column in enumerate(self.config['metadata']):
            filename = '{}-{}.png'.format(data_file.split('.')[0], column)
            self.add_code(self.source['taxa_py_{}'.format(self.analysis_type)].format(file1=data_file,
                                                                                      level=level,
                                                                                      group=column))
            if i == 0:
                self.add_code(self.source['taxa_color_r'].format(level=level))
                self.add_code(self.source['taxa_color_py'].format(level=level))
            self.add_code(self.source['taxa_group_color_py'].format(level=level,
                                                                    group=column))
            self.add_code(self.source['taxa_r'].format(plot=filename,
                                                       level=level,
                                                       group=column))
            self.add_code('Image("{plot}")'.format(plot=filename))
            self.add_markdown(self.source['taxa_caption'])
            self.add_code('Image("taxa_legend_{level}.png")'.format(level=level))
            self.add_code('Image("taxa_{group}_legend_{level}.png")'.format(level=level, group=column))
            self.add_markdown(self.source['page_break'])

    def alpha_plots(self, data_file):
        """
        Create plots for alpha diversity files.
        =======================================
        :data_file: The location of the file to create the plotting code for.
        """
        if self.analysis_type == 'qiime1':
            xaxis = 'SequencesPerSample'
        elif self.analysis_type == 'qiime2':
            xaxis = 'SamplingDepth'
            filename = data_file.split('.')[0] + '.png'
            self.add_markdown('## {f}'.format(f=data_file))
            self.add_code(self.source['alpha_py_{}'.format(self.analysis_type)].format(file1=data_file))
            self.add_code(self.source['alpha_r'].format(file1=filename, xaxis=xaxis))
            self.add_code('Image("{plot}")'.format(plot=filename))
            self.add_markdown(self.source['alpha_caption_{}'.format(self.analysis_type)])

        self.add_code('Image("legend.png")')
        self.add_markdown(self.source['page_break'])

    def beta_plots(self, data_file):
        """
        Create plots for alpha diversity files.
        =======================================
        :data_file: The location of the file to create the plotting code for.
        """
        for column in self.config['metadata']:
            plot = '{}-{}.png'.format(data_file.split('.')[0], column)
            subplot = '{}-%s-%s.png'.format(plot.split('.')[0])
            self.add_markdown('## {f} grouped by {group}'.format(f=data_file,
                                                                 group=column))
            self.add_code(self.source['beta_py'].format(file1=data_file,
                                                        group=column))
            if self.config['metadata_continuous']:
                continuous = 'TRUE'
            else:
                continuous = 'FALSE'
            self.add_code(self.source['beta_r'].format(plot=plot,
                                                       subplot=subplot,
                                                       cat=column,
                                                       continuous=continuous))
            self.add_code('Image("{plot}")'.format(plot=plot))
            self.add_markdown(self.source['beta_caption'])

            self.add_code('Image("{group}-legend.png")'.format(group=column))
            self.add_markdown(self.source['page_break'])
            for x, y in combinations(['PC1', 'PC2', 'PC3'], 2):
                self.add_code('Image("{plot}")'.format(plot=subplot % (x, y)))
                self.add_code('Image("{group}-legend.png")'.format(group=column))
                self.add_markdown(self.source['page_break'])

    def summarize(self):
        """
        Create the python notebook containing the summary of analysis results.
        =====================================================================
        :path: A file path. The path to the directory containing the files to plot
        :files: A dictionary of locations for the files to use when creating plots.
        :execute: A boolean. If True execute the notebook when exporting to PDF, otherwise don't.
        """

        # Add cells for setting up the notebook
        self.add_code(self.source['py_setup'].format(font=(STORAGE_DIR /
                                                           'code_new_roman.otf'),
                                                     titlefont=(STORAGE_DIR /
                                                                'code_new_roman_b.otf')))
        self.add_code(self.source['r_setup'])

        # Add the cells for the OTU summary
        if self.analysis_type == 'qiime1':
            with open(self.run_path / 'biom_table_summary.txt') as f:
                output = f.read().replace('\n', '  \n').replace('\r', '  \r')
                self.add_markdown('# OTU Summary')
                self.add_markdown(output)
                self.add_markdown('To view the full otu table, execute the code cell below')
                self.add_code(self.source['otu_py'])

        # Add the cells for the Taxa summaries
        self.add_markdown('# Taxa Summary')
        for data_file in sorted(self.files['taxa']):
            self.taxa_plots(data_file)
            self.add_code(self.source['legend_py'].format(legend='legend.png'))

        # Add the cells for Alpha Diversity
        self.add_markdown('# Alpha Diversity Summary')
        for data_file in self.files['alpha']:
            self.alpha_plots(data_file)

        # Add the cells for Beta Diversity
        self.add_markdown('# Beta Diversity Summary')
        for data_file in sorted(self.files['beta']):
            if 'dm' in data_file:
                self.add_markdown("## {file1}".format(file1=data_file))
                self.add_code("df = pd.read_csv('{file1}', sep='\t')".format(file1=data_file))
            else:
                self.beta_plots(data_file)

        # Create the notebook and
        meta = {
            'latex_metadata': {
                'author': 'Clemente Lab',
                'affiliation': 'Icahn School of Medicine at Mount Sinai',
                'name': 'MMEDS Analysis Summary',
                'title': 'MMEDS Analysis Summary'
            }
        }
        for cell in self.cells:
            if cell.cell_type == 'code':
                cell.metadata['hide_input'] = True
        nn = nbf.v4.new_notebook(cells=self.cells, metadata=meta)
        return nn

    def write_notebook(self, nn):
        """
        Write the notebook and export it to a PDF.
        ==========================================
        :nn: A python notebook object.
        """
        nbf.write(nn, str(self.run_path / '{}.ipynb'.format(self.name)))

        cmd = 'module load mmeds-stable; ' \
            'jupyter nbconvert --template=revtex.tplx --to=latex {}.ipynb'.format(self.name)
        if self.execute:
            cmd += ' --execute'
            log(cmd)
            run(cmd, shell=True, check=True)

        # Convert to pdf
        cmd = 'pdflatex {name}.tex'.format(name=self.name)
        run(cmd, shell=True, check=True)
        cmd = 'pdflatex {name}.tex'.format(name=self.name)
        run(cmd, shell=True, check=True)

    def create_notebook(self):
        log('Start summary notebook')
        original_path = Path.cwd()
        os.chdir(self.run_path)
        nn = self.summarize()
        self.write_notebook(nn)

        # Switch back to the original directory
        os.chdir(original_path)
