from pathlib import Path
from nbformat import v4
from collections import defaultdict
import nbformat as nbf
from nbconvert import PDFExporter
from nbconvert.preprocessors import ExecutePreprocessor

taxa_r_source = """%%R -i df
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

alpha_py_source = """# Read in the data and metadata files
df = read_csv('{file1}', sep='\t')
mdf = read_csv('qiime_mapping_file.tsv', sep='\t')

# Drop unused columns
df.drop('Unnamed: 0', axis=1, inplace=True)

# Set new indeces
mdf.set_index('#SampleID', inplace=True)
df.set_index('sequences per sample', inplace=True)

# Create groupings based on metadata values
all_means = []    # Stores the dataframes for each group
group_names = []  # Stores the name (Metadata Column) of each group
group_ids = []    # Stores a list of values shared accross groups but unique within (for graphing)

for group_name in mdf.columns:
    grouping = mdf[group_name]
    # Only create groups for values that aren't all the same or all unique
    if grouping.nunique() > 1 and grouping.nunique() < len(grouping):
        # Calculate the means accross iterations
        means = df.groupby('sequences per sample').mean()
        # Join the data and metadata (requires transposing the data)
        joined = means.T.join(grouping, how='outer')
        # Group by metadata value and calculate the mean
        joined_groups = joined.groupby(group_name).mean()
        # Traspose the data frame again and set the indeces to be a seperate column
        all_means.append(joined_groups.T.reset_index(level=0))
        group_names.append(group_name)
        group_ids.append(['color' + str(i) for i in range(grouping.nunique())])
"""

alpha_r_source = """%%R -i all_means -i group_names -i group_ids
# Convert group values from lists to vectors
group_names <- unlist(group_names)
group_ids <- unlist(group_ids)

# Modify the data into long format
dat <- melt(all_means, id='index')

# Rename columns
names(dat) <- c('SequencesPerSample', 'Grouping', 'AverageValue', 'Group')

# Add new columns with group information
DT <- as.data.table(dat)
DT[T, GroupID := group_ids[Grouping]]
DT[T, Group := group_names[Group]]

# Create the plots
p <- ggplot(data = DT, aes(x = SequencesPerSample, y = AverageValue, color=GroupID)) +
     geom_point(stat='identity') +
          geom_line(stat='identity') +
               facet_wrap(~Group) +
                    scale_fill_brewer(palette="Dark2")
                    # Save plots
                    ggsave('{plot}', height = 8, width = 12)
"""


def taxa_plots(path, data_file):
    """ Create plots for taxa summary files. """
    source = "df = read_csv('{file1}', skiprows=1, sep='\t')"
    filename = data_file.split('.')[0] + '.png'
    cells = []
    cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=data_file)))
    cells.append(v4.new_code_cell(source=source.format(file1=data_file)))
    cells.append(v4.new_code_cell(source=taxa_r_source.format(plot=filename)))
    cells.append(v4.new_code_cell(source='Image("{plot}")'.format(plot=filename)))
    return cells


def alpha_plots(path, data_file):
    """ Create plots for alpha diversity files. """
    filename = data_file.split('.')[0] + '.png'
    cells = []
    cells.append(v4.new_markdown_cell(source='## View {f}'.format(f=data_file)))
    cells.append(v4.new_code_cell(source=alpha_py_source.format(file1=data_file)))
    cells.append(v4.new_code_cell(source=alpha_r_source.format(plot=filename)))
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
    py_setup = [
        "from pandas import read_csv",
        "import rpy2.rinterface",
        "from warnings import filterwarnings",
        "from IPython.display import Image",
        "filterwarnings('ignore', category=rpy2.rinterface.RRuntimeWarning)"
    ]
    r_setup = [
        "%%R",
        "require(ggplot2)",
        "require(reshape2)",
        "require(data.table)"
    ]
    otu_source = [
        "df = read_csv('{filename}', skiprows=1, header=0, sep='\t')",
        "df.set_index('{index}', inplace=True)",
        "df.iloc[:5, :5]"
    ]
    otu_source = '\n'.join(otu_source).format(filename='otu_table.tsv', index='taxonomy')

    cells = []

    with open(path / 'biom_table_summary.txt') as f:
        output = f.read().replace('\n', '  \n').replace('\r', '  \r')

    # Add all the cells containing the different files
    cells.append(v4.new_markdown_cell(source='# Notebook Setup'))
    cells.append(v4.new_code_cell(source='\n'.join(py_setup)))
    cells.append(v4.new_code_cell(source="%load_ext rpy2.ipython"))
    cells.append(v4.new_code_cell(source='\n'.join(r_setup)))
    cells.append(v4.new_markdown_cell(source='# OTU Summary'))
    cells.append(v4.new_markdown_cell(source=output))
    cells.append(v4.new_markdown_cell(source='To view the full otu table, execute the code cell below'))
    cells.append(v4.new_code_cell(source=otu_source))
    cells.append(v4.new_markdown_cell(source='# Taxa Diversity Summary'))
    for data_file in files['taxa']:
        cells += taxa_plots(path, data_file)
    cells.append(v4.new_markdown_cell(source='# Alpha Diversity Summary'))
    for data_file in files['alpha']:
        cells += alpha_plots(path, data_file)
    cells.append(v4.new_markdown_cell(source='# Beta Diversity Summary'))
    for data_file in files['beta']:
        if 'dm' in data_file:
            cells.append(v4.new_markdown_cell(source="## View {file1}".format(file1=data_file)))
            cells.append(v4.new_code_cell(source="read_csv('{file1}')".format(file1=data_file)))

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
    nbf.write(nn, str(path / 'analysis2.ipynb'))

    exp = PDFExporter()
    if execute:
        ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
        ep.preprocess(nn, {'metadata': {'path': '{path}/'.format(path=path)}})

    (pdf_data, resources) = exp.from_notebook_node(nn)
    with open(path / 'notebook.pdf', 'wb') as f:
        f.write(pdf_data)


execute = True
path = Path('/home/david/Work/data-mmeds/summary')

nn = summerize(path, execute)
write_notebook(nn)
