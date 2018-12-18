from pathlib import Path
from nbformat import v4
from collections import defaultdict
import nbformat as nbf
from nbconvert import PDFExporter
from nbconvert.preprocessors import ExecutePreprocessor

r_source = """%%R -i df
rndf <- melt(df, id="X.OTU.ID")
p <- ggplot(rndf, aes(x = variable, y = value, fill = X.OTU.ID)) +
     geom_bar(stat = "identity") +
     ggtitle("Taxa Summary") +
     labs(x = "Sample ID") +
     theme(text = element_text(size = 8.5,
                               face = "bold"),
           element_line(size = 0.1)) +
     scale_y_discrete(name = "OTU Percentage",
                      limits = c(0, 1),
                      expand = c(0, 0)) +
     theme(legend.text=element_text(size=7),
           legend.key.size = unit(0.1, "in"),
           legend.position = "bottom",
           legend.direction="vertical",
           plot.title = element_text(hjust = 0.5))

ggsave("{plot}", height = 8, width = 12)
"""


def taxa_plots(path, data_file):
    """ Create plots for taxa summary files. """
    source = "df = read_csv('{file1}', skiprows=1, sep='\t')"
    filename = data_file.split('.')[0] + '.png'
    cells = []
    cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=data_file)))
    cells.append(v4.new_code_cell(source=source.format(file1=data_file)))
    cells.append(v4.new_code_cell(source=r_source.format(plot=filename)))
    cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
    return cells


def alpha_plots(path, data_file):
    """ Create plots for alpha diversity files. """
    source = "df = read_csv('{file1}', skiprows=1, sep='\t')"
    filename = data_file.split('.')[0] + '.png'
    cells = []
    cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=data_file)))
    cells.append(v4.new_code_cell(source=source.format(file1=data_file)))
    cells.append(v4.new_code_cell(source=r_source.format(plot=filename)))
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

    otu_source = [
        "from pandas import read_csv",
        "import rpy2.rinterface",
        "from IPython.display import Image",
        "df = read_csv('{filename}', skiprows=1, header=0, sep='\t')",
        "df.set_index('{index}', inplace=True)",
        "df.head()"

    ]
    otu_source = '\n'.join(otu_source).format(filename='otu_table.tsv', index='taxonomy')
    alpha_source = [
        "df = read_csv('chao1.txt', sep='	')",
        "df.drop('Unnamed: 0', axis=1, inplace=True)"
    ]   

    plot_source = [
        "%%R",
        "require(ggplot2)",
        "require(reshape2)"
    ]
    plot_source = '\n'.join(plot_source)

    cells = []

    with open(path / 'biom_table_summary.txt') as f:
        output = f.read().replace('\n', '  \n').replace('\r', '  \r')

    # Add all the cells containing the different files
    cells.append(v4.new_markdown_cell(source='# OTU Summary'))
    cells.append(v4.new_markdown_cell(source=output))
    cells.append(v4.new_code_cell(source="%load_ext rpy2.ipython"))
    cells.append(v4.new_code_cell(source=plot_source))
    cells.append(v4.new_markdown_cell(source='To view the full otu table, execute the code cell below'))
    cells.append(v4.new_code_cell(source=otu_source))
    cells.append(v4.new_markdown_cell(source='# Taxa Diversity Summary'))
    for data_file in files['taxa']:
        cells += taxa_plots(path, data_file)
    cells.append(v4.new_markdown_cell(source='# Alpha Diversity Summary'))
    for f in files['alpha']:
        cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=f)))
        cells.append(v4.new_code_cell(source=alpha_source.format(file1=f)))
        if 'chao' in f:
            cells.append(v4.new_code_cell(source=plot_source))
    cells.append(v4.new_markdown_cell(source='# Beta Diversity Summary'))
    for f in files['beta']:
        if 'dm' in f:
            cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=f)))
            cells.append(v4.new_code_cell(source=alpha_source.format(file1=f)))

    nn = nbf.v4.new_notebook(cells=cells)
    meta = {
        'metadata': {
            'authors': [{'name': 'David Wallach', 'email': 'david.wallach@mssm.edu'}],
            'name': 'MMEDS Analysis Summary',
            'title': 'MMEDS Analysis Summary'
        }
    }
    nn.update(meta)

    # nn = nbf.read(str(path / 'analysis.ipynb'), as_version=4)

    return nn


def write_notebook(nn):
    nbf.write(nn, str(path / 'analysis.ipynb'))

    exp = PDFExporter()
    if execute:
        ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
        ep.preprocess(nn, {'metadata': {'path': '{path}/'.format(path=path)}})

    (pdf_data, resources) = exp.from_notebook_node(nn)
    with open(path / 'notebook.pdf', 'wb') as f:
        f.write(pdf_data)


execute = False
path = Path('/home/david/Work/data-mmeds/summary')

nn = summerize(path, execute)
write_notebook(nn)
