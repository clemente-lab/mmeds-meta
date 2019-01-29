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


def summarize_qiime(path, files, load_info, config_file, tool):
    """ Wrapper for the different qiime summarizers."""

    config = load_config(config_file.read_text(), path)
    if tool == 'qiime1':
        summary_files = summarize_qiime1(path, files, load_info, config)
    elif tool == 'qiime2':
        summary_files = summarize_qiime2(path, files, load_info, config)

    # Create the summary
    create_summary_notebook(analysis_type=tool,
                            files=summary_files,
                            execute=True,
                            name='analysis',
                            run_path=path / 'summary',
                            config=config)

    # Create a zip of the summary
    result = make_archive(path / 'summary',
                          format='zip',
                          root_dir=path,
                          base_dir='summary')
    log('Create archive of summary')
    log(result)

    log('Summary completed succesfully')
    return path / 'summary/analysis.pdf'


def summarize_qiime1(path, files, load_info, config):
    """
    Create summary of analysis results
    """
    log('Run summarize')
    diversity = files['diversity_output']
    summary_files = defaultdict(list)

    # Convert and store the otu table
    cmd = '{} biom convert -i {} -o {} --to-tsv --header-key="taxonomy"'
    cmd = cmd.format(load_info,
                     files['otu_output'] / 'otu_table.biom',
                     path / 'otu_table.tsv')
    log(cmd)
    run(cmd, shell=True, check=True)

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
    return summary_files


def summarize_qiime2(path, files, load_info, config):
    """ Create summary of the files produced by the qiime2 analysis. """
    log('Start Qiime2 summary')

    # Setup the summary directory
    summary_files = defaultdict(list)

    # Get Taxa
    cmd = '{} qiime tools export {} --output-dir {}'.format(load_info,
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
        cmd = '{} qiime tools export {} --output-dir {}'.format(load_info,
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
        cmd = '{} qiime tools export {} --output-dir {}'.format(load_info,
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
    return summary_files


def create_summary_notebook(analysis_type, files, execute, name, run_path, config):
    """
    Create the summary PDF for qiime1 analysis
    ==========================================
    :files: A dictionary of locations for the files to use when creating plots.
    :execute: A boolean. If True execute the notebook when exporting to PDF, otherwise don't.
    :name: A string. The name of the notebook and PDF document.
    :run_path: A file path. The path to the directory containing all the summary files.
    :config: A dictionary. Contains the parameters from the config file for the analysis.
    """

    # Used to store the notebook cells
    cells = []

    def add_code(source):
        """A wrapper function to clean up all the calls to add code to cells."""
        cells.append(v4.new_code_cell(source=source))

    def add_markdown(source):
        """A wrapper function to clean up all the calls to add markdown to cells."""
        cells.append(v4.new_markdown_cell(source=source))

    def taxa_plots(data_file, level):
        """
        Create plots for taxa summary files.
        ====================================
        :data_file: The location of the file to create the plotting code for.
        """
        add_markdown('## OTU level {level}'.format(level=level))
        for i, column in enumerate(config['metadata']):
            filename = '{}-{}.png'.format(data_file.split('.')[0], column)
            add_code(source['taxa_py_{}'.format(analysis_type)].format(file1=data_file,
                                                                       level=level,
                                                                       group=column))
            if i == 0:
                add_code(source['taxa_color_r'].format(level=level))
                add_code(source['taxa_color_py'].format(level=level,
                                                        font=(STORAGE_DIR /
                                                              'code_new_roman.otf'),
                                                        titlefont=(STORAGE_DIR /
                                                                   'code_new_roman_b.otf'),
                                                        abundance_threshold=config['abundance_threshold'],
                                                        fontsize=config['font_size']))
                add_code(source['taxa_group_color_py'].format(level=level,
                                                              abundance_threshold=config['abundance_threshold'],
                                                              group=column))
                add_code(source['taxa_r'].format(plot=filename,
                                                 level=level,
                                                 group=column))
                add_code('Image("{plot}")'.format(plot=filename))
                add_markdown(source['taxa_caption'])
                add_code('Image("taxa_legend_{level}.png")'.format(level=level))
                add_code('Image("taxa_{group}_legend_{level}.png")'.format(level=level,
                                                                           group=column))
                add_markdown(source['page_break'])

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
        add_markdown('## {f}'.format(f=data_file))
        add_code(source['alpha_py_{}'.format(analysis_type)].format(file1=data_file))
        add_code(source['alpha_r'].format(file1=filename, xaxis=xaxis))
        add_code('Image("{plot}")'.format(plot=filename))
        add_markdown(source['alpha_caption_{}'.format(analysis_type)])
        add_code('Image("legend.png")')
        add_markdown(source['page_break'])

    def beta_plots(data_file):
        """
        Create plots for alpha diversity files.
        =======================================
        :data_file: The location of the file to create the plotting code for.
        """
        for column in config['metadata']:
            plot = '{}-{}.png'.format(data_file.split('.')[0], column)
            subplot = '{}-%s-%s.png'.format(plot.split('.')[0])
            add_markdown('## {f} grouped by {group}'.format(f=data_file,
                                                            group=column))
            add_code(source['beta_py'].format(file1=data_file,
                                              group=column))
            add_code(source['beta_r'].format(plot=plot,
                                             subplot=subplot,
                                             cat=column))
            add_code('Image("{plot}")'.format(plot=plot))
            add_markdown(source['beta_caption'])
            add_code('Image("{group}-legend.png")'.format(group=column))
            add_markdown(source['page_break'])
            for x, y in combinations(['PC1', 'PC2', 'PC3'], 2):
                add_code('Image("{plot}")'.format(plot=subplot % (x, y)))
                add_code('Image("{group}-legend.png")'.format(group=column))
                add_markdown(source['page_break'])

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

        # Add cells for setting up the notebook
        add_code(source['py_setup'])
        add_code(source['r_setup'])

        # Add the cells for the OTU summary
        if analysis_type == 'qiime1':
            with open(path / 'biom_table_summary.txt') as f:
                output = f.read().replace('\n', '  \n').replace('\r', '  \r')
            add_markdown('# OTU Summary')
            add_markdown(output)
            add_markdown('To view the full otu table, execute the code cell below')
            add_code(source['otu_py'])

        # Add the cells for the Taxa summaries
        add_markdown('# Taxa Summary')
        for data_file in sorted(files['taxa']):
            level = data_file.split('.')[0][-1]
            if level in config['taxa_levels']:
                taxa_plots(data_file, level)
        add_code(source['legend_py'].format(fontfile=STORAGE_DIR / 'ABeeZee-Regular.otf',
                                            fontsize=config['font_size'],
                                            legend='legend.png'))

        # Add the cells for Alpha Diversity
        add_markdown('# Alpha Diversity Summary')
        for data_file in files['alpha']:
            alpha_plots(data_file)

        # Add the cells for Beta Diversity
        add_markdown('# Beta Diversity Summary')
        for data_file in sorted(files['beta']):
            if 'dm' in data_file:
                add_markdown("## {file1}".format(file1=data_file))
                add_code("df = read_csv('{file1}', sep='\t')".format(file1=data_file))
            else:
                beta_plots(data_file)

        # Create the notebook and
        meta = {
            'latex_metadata': {
                'author': 'Clemente Lab',
                'affiliation': 'Icahn School of Medicine at Mount Sinai',
                'name': 'MMEDS Analysis Summary',
                'title': 'MMEDS Analysis Summary'
            }
        }
        for cell in cells:
            if cell.cell_type == 'code':
                cell.metadata['hide_input'] = True
        nn = nbf.v4.new_notebook(cells=cells, metadata=meta)
        return nn

    def write_notebook(nn):
        """
        Write the notebook and export it to a PDF.
        ==========================================
        :nn: A python notebook object.
        """
        nbf.write(nn, str(path / '{}.ipynb'.format(name)))
        cmd = 'jupyter nbconvert --template=revtex.tplx --to=latex {}.ipynb'.format(name)
        if execute:
            cmd += ' --execute'
        log(cmd)
        run(cmd, shell=True, check=True)

        # Convert to pdf
        cmd = 'pdflatex {name}.tex'.format(name=name)
        run(cmd, shell=True, check=True)
        cmd = 'pdflatex {name}.tex'.format(name=name)
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
