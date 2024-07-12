# This is the process for creating a functional summary environment

### Create a conda environment named 'jupyter':
`conda env create -f conda_env_files/jupyter.yaml'

# Then activate the environment and run MMED's setup.py script:
`conda activate jupyter`
`python setup.py install`

# add jupyter module to module folder
mmeds-meta/modules should be copied to ~/.modules/modulefiles

this seems to work for installing dependancies, but not updating code:
pip install git+https://github.com/clemente-lab/mmeds-meta@master

to update code changes while testing, use: `python setup.py install` or as I do: `python setup.py install --user` to install into my user directory

# might need to run, seemed necessary for github actions
pip install cryptography

# With R version 3.5.1, run the following:

R
install.packages("GGally",dependencies=TRUE)
install.packages("ggrepel",dependencies=TRUE)
install.packages("RColorBrewer")
# older versions of R
install.packages("ggplot")
# or for newer R versions
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
