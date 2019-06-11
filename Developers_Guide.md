# MMEDS Developers Guide

## General Overview

## Server

## Database

### Mongo 

### MySQL


## Tools

### Qiime1

### Qiime2

## Summary

### Overview

The setup for creating the summary documents is more complicated than I would like but it fits the criteria for this project better than any other solution I could come up with. There are several stages involved in creating the final summary. It starts with `mmeds/summary.py`. This file contains functions that gather all the desired files after an analysis is run. It moves these files into a directory called `summary` in the root directory of the analysis being summarized. The functions then create a python notebook (extension `.ipynb`) in that directory. The code in the notebook is primarily taken from pre-written code blocks in `mmeds/resources/summary_code.txt`. These code blocks are a combination of R and Python that parse and create plots from the results of the analysis. The legends are generated separately however.

Before the final PDF is produced, the notebook will be executed and converted to latex using `jupyter nbconvert ...`. This conversion involves a template file (the original is found at `mmeds/resources/revtex.tplx`). This template is modified during the execution of the notebook. It is updated with the colors and values necessary for creating the legends. This information is then written into the latex version of the notebook. That `.tex` file is then converted to a PDF by executing `pdflatex {file}.tex` twice. Running the command twice is necessary for some of the template formatting to show up. I don't know why. If you can get clickable header links and legends to work without it feel free to change that.



### Notebook
