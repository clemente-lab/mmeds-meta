# This is the process for creating a functional summary environment

# First create a conda environment named 'jupyter' from the environment file located at `/docs/environment.yml`

`conda env create --file environment.yml`

# Then activate the environment and run the rest of these commands in it
`conda activate jupyter`

# Then install the necessary R packages and version of nbconvert from conda-forge
# NB: nbconvert was previously kept at version 5.6.1, now kept current
`conda install nbconvert r-ggplot2 r-ggally r-ggrepel r-rcolorbrewer -c conda-forge`

# Now use pip to install the PDF template for jupyter and the Pillow python library

`pip install nb_pdf_template pillow`

# Once all that is installed create a jupyter kernel from the current environment

`python -m ipykernel install --user --name jupyter --display-name="Jupyter"`

# Install necessary latex stuff

## Fedora
`sudo dnf install texlive texlive-revtex texlive-braket`

## Ubuntu (I think, you may have to install more packages)
`sudo apt install texlive-latex texlive-latex-recommended`
