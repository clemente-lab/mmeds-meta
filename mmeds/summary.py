from pathlib import Path
from nbformat import v4
from collections import defaultdict
from subprocess import run, CalledProcessError
from itertools import combinations
from shutil import copy, rmtree, make_archive

import nbformat as nbf
import os
from mmeds.config import STORAGE_DIR
from mmeds.util import log, load_config, setup_environment


def summarize_qiime(summary_path, tool):
    """ Handle setup and running the summary for the two qiimes """
    path = Path(summary_path)

    # Load the files
    files = {}
    lines = (path / 'file_index.tsv').read_text().strip().split('\n')
    for line in lines:
        parts = line.split('\t')
        files[parts[0]] = Path(parts[1])

    # Create the summary directory
    if not files['summary'].is_dir():
        files['summary'].mkdir()

    # Get the font files
    copy(STORAGE_DIR / 'code_new_roman.otf', files['summary'] / 'font_file.otf')
    copy(STORAGE_DIR / 'code_new_roman_b.otf', files['summary'] / 'font_file_bold.otf')

    # Get the mapping file
    copy(files['mapping'], files['summary'])
    copy(files['metadata'], files['summary'] / 'metadata.tsv')
    copy(path / 'config_file.txt', files['summary'] / 'config_file.txt')

    # Get the template
    copy(STORAGE_DIR / 'revtex.tplx', files['summary'])

    # Load the configuration
    config = load_config((path / 'config_file.txt').read_text(), files['metadata'])

    if tool == 'qiime1':
        summarize_qiime1(path, files, config)
    elif tool == 'qiime2':
        summarize_qiime2(path, files, config)


def summarize_qiime1(path, files, config):
    """
    Create summary of analysis results
    """
    def move_files(path, category):
        """ Collect the contents of all files match the regex in path """
        log('Move files {}'.format(category))
        data_files = diversity.glob(path.format(depth=config['sampling_depth']))
        for data in data_files:
            copy(data, files['summary'])
            summary_files[category].append(data.name)

    log('In summarize_qiime1')
    diversity = files['diversity_output']
    summary_files = defaultdict(list)

    move_files('biom_table_summary.txt', 'otu')                       # Biom summary
    move_files('arare_max{depth}/alpha_div_collated/*.txt', 'alpha')  # Alpha div
    move_files('bdiv_even{depth}/*.txt', 'beta')                      # Beta div
    move_files('taxa_plots/*.txt', 'taxa')                            # Taxa summary

    # Get the environment
    new_env = setup_environment('qiime/1.9.1')

    # Convert and store the otu table
    cmd = ['biom', 'convert', '--to-tsv', '--header-key=taxonomy',
           '-i', str(files['otu_output'] / 'otu_table.biom'),
           '-o', str(path / 'otu_table.tsv')]
    try:
        run(cmd, capture_output=True, env=new_env, check=True)
    except CalledProcessError as e:
        log(e)
        raise e
    log('biom convert Finished')

    # Add the text OTU table to the summary
    copy(path / 'otu_table.tsv', files['summary'])
    summary_files['otu'].append('otu_table.tsv')

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


def summarize_qiime2(path, files, config):
    """ Create summary of the files produced by the qiime2 analysis. """
    log('Start Qiime2 summary')

    # Get the environment
    new_env = setup_environment('qiime2/2019.1')

    # Setup the summary directory
    summary_files = defaultdict(list)

    # Get Taxa
    cmd = ['qiime', 'tools', 'export',
           '--input-path', str(files['taxa_bar_plot']),
           '--output-path', str(path / 'temp')]
    run(cmd, env=new_env, check=True)
    taxa_files = (path / 'temp').glob('level*.csv')
    for taxa_file in taxa_files:
        copy(taxa_file, files['summary'])
        summary_files['taxa'].append(taxa_file.name)
    rmtree(path / 'temp')

    # Get Beta
    beta_files = files['core_metrics_results'].glob('*pcoa*')
    for beta_file in beta_files:
        cmd = ['qiime', 'tools', 'export',
               '--input-path', str(beta_file),
               '--output-path', str(path / 'temp')]
        run(cmd, env=new_env, check=True)
        dest_file = files['summary'] / (beta_file.name.split('.')[0] + '.txt')
        copy(path / 'temp' / 'ordination.txt', dest_file)
        log(dest_file)
        summary_files['beta'].append(dest_file.name)
    rmtree(path / 'temp')

    # Get Alpha
    cmd = ['qiime', 'tools', 'export',
           '--input-path', str(files['alpha_rarefaction']),
           '--output-path', str(path / 'temp')]
    run(cmd, env=new_env, check=True)
    for metric in ['shannon', 'faith_pd', 'observed_otus']:

        metric_file = path / 'temp/{}.csv'.format(metric)
        copy(metric_file, files['summary'])
        summary_files['alpha'].append(metric_file.name)
    rmtree(path / 'temp')

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
        self.env = setup_environment('mmeds-stable')

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
        for column in sorted(self.config['metadata']):
            plot = '{}-{}.png'.format(data_file.split('.')[0], column)
            subplot = '{}-%s-%s.png'.format(plot.split('.')[0])
            self.add_markdown('## {f} grouped by {group}'.format(f=data_file,
                                                                 group=column))
            self.add_code(self.source['beta_py'].format(file1=data_file,
                                                        group=column))
            contin = str(self.config['metadata_continuous'][column]).capitalize()
            self.add_code(self.source['beta_r'].format(plot=plot,
                                                       subplot=subplot,
                                                       cat=column,
                                                       continuous=contin))
            self.add_code('Image("{plot}")'.format(plot=plot))
            self.add_markdown(self.source['beta_caption'])

            self.add_code('Image("{group}-legend.png")'.format(group=column))
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

        log('in notebook')
        log(self.files)
        # Add cells for setting up the notebook
        self.add_code(self.source['py_setup'].format(font='font_file.otf',
                                                     analysis_type=self.analysis_type,
                                                     titlefont='font_file_bold.otf'))
        self.add_code(self.source['r_setup'])

        # Add the cells for the OTU summary
        if self.analysis_type == 'qiime1':
            with open(self.run_path / 'biom_table_summary.txt') as f:
                output = f.read().replace('\n', '  \n').replace('\r', '  \r')
                self.add_markdown('# OTU Summary')
                self.add_markdown(output)
                self.add_markdown('To view the full otu table, execute the code cell below')
                self.add_code(self.source['otu_py'])

        # Get only files for the requested taxa levels
        included_files = []
        for taxa_level in self.config['taxa_levels']:
            for taxa_file in self.files['taxa']:
                if str(taxa_level) in taxa_file:
                    included_files.append(taxa_file)

        # Add the cells for the Taxa summaries
        self.add_markdown('# Taxa Summary')
        for data_file in included_files:
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
        try:
            nbf.write(nn, str(self.run_path / '{}.ipynb'.format(self.name)))
            cmd = 'jupyter nbconvert --template=revtex.tplx --to=latex'
            cmd += ' {}.ipynb'.format(self.name)
            if self.execute:
                cmd += ' --execute'
                # Mute output
                #  cmd += ' &>/dev/null;'
            log('Convert notebook to latex')
            output = run(cmd.split(' '), check=True, env=self.env, capture_output=True)

            log('Convert latex to pdf')
            # Convert to pdf
            cmd = 'pdflatex {name}.tex'.format(name=self.name)
            # Run the command twice because otherwise the chapter
            # headings don't show up...
            output = run(cmd.split(' '), check=True)
            output = run(cmd.split(' '), check=True)
        except RuntimeError:
            print(output)
            log(output)

    def create_notebook(self):
        log('Start summary notebook')
        original_path = Path.cwd()
        os.chdir(self.run_path)
        nn = self.summarize()
        self.write_notebook(nn)

        # Switch back to the original directory
        os.chdir(original_path)
