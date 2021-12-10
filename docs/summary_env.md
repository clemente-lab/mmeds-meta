# This is the process for creating a functional summary environment

# First create a conda environment named 'jupyter':
`conda env create -f conda_env_files/jupyter.yaml'

# Then activate the environment and run MMED's setup.py script:
`conda activate jupyter`
`python setup.py install`

# With R version 3.5.1, run the following:

R
install.packages("GGally",dependencies=TRUE)
install.packages("ggrepel",dependencies=TRUE)
install.packages("RColorBrewer")
install.packages("ggplot2")

quit()

# Once all that is installed create a jupyter kernel from the current environment:

`python -m ipykernel install --user --name jupyter --display-name="Jupyter"`

### Install latex to run pdflatex command:
# on minerva
module load texlive/2018

# Fedora
`sudo dnf install texlive texlive-revtex texlive-braket`

# Ubuntu
`sudo apt install texlive-latex texlive-latex-recommended`

# trying to mimic minerva by downloading texlive-core 2018:
https://anaconda.org/conda-forge/texlive-core/files
conda install -c conda-forge texlive-core=20180414


### troubleshooting;
things I at some point ran directly:
conda install -c anaconda pandas=1.2.3
conda install -c r rpy2=3
conda install -c anaconda pillow
pip install simplegeneric
conda install -c conda-forge importlib-metadata=3
conda install --force-reinstall jupyter_client
conda install -c conda-forge jupyter_client=6.1.12
conda install -c anaconda ipykernel
conda install -c conda-forge backports.zoneinfo
