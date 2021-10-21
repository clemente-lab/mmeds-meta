# MMEDS Developers Guide

## General Overview

Author's Note:
    MMEDS is my most beloved child. You best treat it right or there will be consequences. Specifically it will quickly become
    increasingly difficult to maintain. Since you'll be the one (or two) maintaining it, it's in your best interest to keep
    the quality of code high....
    Also I will come 4 u.

## Server
Found at `mmmeds/server.py`

The server is broken up into six application "sections". Each gets its own class, all of which inherit from the `MMEDSBase` class. The final `MMEDSServer` class creates an instance of each of the sections and acts as the main entry point to the application. Each class has a number of methods. Those that are decorated with `@cp.expose` are actual webpages that the user can access. Each of these will, after some server side processing, assign a bunch of HTML as a string to the variable `page` and return that page. This will be what the user sees.

Through out most of MMEDS variables are written using underscores, as is typical Python style. To distinguish arguments that are direct webpage inputs from the user they are usually written in camel case. I've tried to be consistent with this but there may be a few locations where this doesn't hold true.



## Database

There are a few significant files that have to do with Database operations.

### database.py
### metadata_uploader.py
### metadata_adder.py
### sql_builder.py
### documents.py

### Mongo 

### MySQL

## Tools
All tools in MMEDS inherit from the `Tool` class in `mmeds/tools/tool.py`. All the general Tool management happens in this class. The only methods in the inheriting classes are those for commands specific to each analysis tool. 

### Untested Functionality
There is a lot of functionality that has been developed for the Tool class at one point or another. Not all of it has been maintained. Analysis Restarting, Sub-Analyses, and Additional Analyses fall into this category.

#### Restarting Analysis
Restarting analysis allows an analysis to be selected to run again starting from the last successful MMEDS_STAGE as indicated by the echo statement in the job file. However for this to work, the files generated after that stage of the analysis need to be removed or qiime will complain. I had set it so those files were automatically cleared when an analysis failed but quickly that become a pain when debugging analysis issues. Two possible fixes for this are
1) Changing the clean up to happen when the analysis is restarted, so the files remain for the period of time where one would be debugging them.
2) Add parameters to the qiime commands to overwrite existing files.

On the whole I like solution 1 better, but priorities in the lab shifted and I never ended up implementing it. There are still methods and other functionality in MMEDS that refers to this restarting capability, though there is no way currently to directly restart analysis from the web app.

#### Sub-Analysis
This is was a big thing Jose wanted for a while. so there is quite a bit of functionality built around it. I'm not sure if it currently works or not. My guess would be it doesn't but could be fixed without too much effort. The idea is that often people want to compare results specifically within certain groups. SO for example, if a study has both gut and nasal samples, often people would want one summary of just the nasal results and one for just the gut.
The workflow for this is as follows,
- The user selections some columns for sub-analysis via the config file.
- When setting up the main analysis the tool class creates child processes for each group within the specified columns.
- These children wait on the main analysis process to import, demux, and create the initial table (DADA2 or DeBlur). The child process then creates it's own analysis folder that links to the data files from the parent analysis.
- Each child process filters the table so it only contains samples from the desired group and then proceeds as would any other analysis.

This functionality did work the last time it was tested but that was more than a year ago as of 2021-10-13. Any references to 'child', 'children', 'parent', 'sub-analysis', etc in the Tool class refer to this functionality. As with analysis restarting my guess is that it doesn't work currently but it wouldn't take too much effort to get it to work again.

I will say though, this can be a bit of a headache to work on. It's two levels of processes removed from whatever initially started python running. This means you usually can't use a debugger to see what's going on directly. This also means that
unlike regular analysis processes the Watcher can't see what's happening with a child process. Only the primary analysis
process which spawned the child can view it's status. This creates a few issues. The primary one being that the primary
analysis needs to stick around to monitor it's children, so if the Primary analysis fails, the children are orphaned and
someones has to go manually check on their status. The fix I was working on for htis was to have the primary process pass
instructions for creating the sub-analysis (child) to the watcher rather than creating it directly. This in turn creates
some issues however as the child needs to know the location of various files from the primary analysis as well as some
other things. I don't think I ever fully implemented it.

There may be better solutions at this point for achieving the desired functionality.

#### Additional Analysis
This is some functionality similar to that for creating sub-analyses but with some key differences. Where a sub-analysis runs the same tool (generally Qiime1 or Qiime2) on a subset on the data, an additional analysis is an analysis with a different tool performed on some data generated by the primary analysis. For example, a primary analysis of Qiime2 could have an additional analysis of SparCC, so that would automatically run SparCC on the OTU table generated during the Qiime2 run (ASV tables can bite me). As with Restarting analysis and Sub-analysis, ever since I stopped being able to maintain analysis tests as part of the automated testing suite I'm not sure if this works or not. The method `create_additional_analysis` shares a lot of code with `create_sub_analysis` but the differences were significant enough that I never managed to unify them. Also this stuff just stopped being a priority after the old nodes were retired and I had to move MMEDS to a WSGI app on HPC's apache setup.


### Qiime1
Qiime1 is not often used these days. Most primary analysis is done with Qiime2. However qiime1 still offers some functionality that Qiime2 never implemented. As of (10/19/2021) I think the qiime1 tool class doesn't work on minerva. The minerva Qiime1 install requires some finagling to get it to run and that hasn't been added to the class here. For more info on Qiime1 see here (http://qiime.org/). It's been a few years since I've been able to create a fresh, functional Qiime1 install. Not since Python2 went EOL. Apparently someone was able to install it in a VM? Not sure why that would help but w/e (https://forum.qiime2.org/t/qiime1-installation/19309/7).

Since it has mostly been superceded for our use case this functionality may be deprecated.

### Qiime2
This is by far the most used tool in MMEDs. It's also the largest class since a full qiime2 run requires quite a few commands. They are all fairly well commented and I think most MMEDs devs are relatively familiar with them at this point. For more info see the Qiime2 site (https://qiime2.org/). MMEDs uses version 2020.8.1, the most recent version installed on Minerva. There are a number of parameters, like `p_trim_length` that we might want to make selectable via the config file. Not sure if there's too much more needs said about this.

### PiCRUSt1
PiCRUSt does some stuff. Probably. It predicts metagenomes or something. It's currently being replaced by PiCRUSt2 which is python3 based but that isn't finished yet so we still use PiCRUSt1. Find out more about this exicting project here (https://picrust.github.io/picrust/install.html)

PiCRUSt2 has officially been published so in future we should transition to using that version.

### SparCC
SparCC generates a sparsity matrix for a given OTU input. It creates a certain number of permutations and iterates over then a given number of times. These parameters can be set in the config file for an analysis. The permutations are shuffled versions of the data set, created in the `make_bootstraps` step. The interations are used to generate pseudo p values for the shuffle datasets, this is the `pseudo_pvals` step. For more information on the tool look here (https://github.com/bio-developer/sparcc)
SparCC generates a co-occurrence network (nodes, edges, length of edges). This is later loaded into Cytoscape for visualization, having an automated way of generating the network would be highly desirable but it would require some time to understand Cytoscape's CLI and parameters.

NOTE: SparCC is poorly coded. If you want to set it up locally and have the scripts as part of your path you're going to have to modify some of them by adding a `#!/usr/bin/python` header, and setting their execute flag in bash. By default you can only run the scripts by typing out the full path.


### Lefse

What does this tool even do? Make a cladogram? TF is a cladogram? Whatever it is lefse makes one. Using a modified OTU table as inputs.There's an example called `lefse_table.tsv` in `test_files`. There are some settings for 'subclass' and 'subjects', these effect which metadata column is used for grouping the final output. More info can be found here (https://github.com/SegataLab/lefse) and here (https://pubmed.ncbi.nlm.nih.gov/21702898/). Nothing too complicated about the methods in this class.



## Solo Files

### formatter.py


#### What does this do?
This file is a bit of a mish-mash of things at the moment. It contains predefined queries used to update Aliquots and Samples in existing studies. These are global strings that are imported elsewhere. The specifics of the query are formatted into each of them.
The other thing in this file are formatting functions for the HTML the server generates. `build_xxx_...`. These are used in server.py to build out html tables that are used in multiple locations throughout the web application.
Eventually I think these thing should each get their own file but for now each file would be pretty small.

### authentication.py
This file contains functions used to manage user accounts. Adding new users, resetting passwords, etc. If it has to do with a user account the function should be in here.

### error.py
This file contains all the error classes used in MMEDs. They all inherit from the MmedsError base class. Some of them take string arguments as specific messages they display. Most of them have hard coded default messages.

### secrets.py
This file contains the authentication information for accounts on Minerva. The version of this file that get uploaded to github is a dummy version that doesn't contain the actual account info. The real version stays on minerva, with a backup of it in the base directory of the MMEDs allocation.

### logger.py
This file contains the mmeds Logger class. It takes advantage of the built in python logging library. The log levels it implements are `info`, `debug`, `warning`, and `error`. This can likely be improved in the future.

### spawn.py
This file contains the Watcher class and associated functionality. The Watcher class inherits from a Python Manager class as
runs as it's own process. It does all the process monitoring and management for mmeds. I think most of the methods are fairly straightforward and appropriately named. The most complex are the `handle_...` methods. These perform the actual creation and starting of the processes spawned for analysis, uploads, etc. For each the watcher passes in the n-tuple it received in the watch queue and generates the process from there.

### validate.py
As the name suggests this contains the classes for performing metadata validation. The Validator class is currently only used to validate the full subject and specimen mapping files. For additional metadata files (like those used to add new Aliquots and Samples to an existing study), the function `valid_additional_file` is used. Eventually this functionality should be incorporated into the main Validator class, with parameters to set if the input file is a full or partial (additional) metadata file.

`validate_mapping_file` serves as a wrapper of sorts for the Validator class. It just passes along the arguments and starts the class running. `cast_columns` is used by `valid_additional_file` to cast columns. Shocking I know.

#### Validator
The Validator class doesn't do any single thing that's especially complex. It just has to do a lot of simple things together making for a somewhat complex class. The basic idea is that there are two lists that are properties of the object, `self.errors` and `self.warnings`. As the class runs on the provided metadata file any problem it encounters with the metadata will be recorded as an error, which will prevent the upload from continuing, or a warning which will inform the user but give them the option to proceed.

There are a lot of specific checks and I'm not going to get into them all here. The basic control flow is `run` -> `check_table` -> `check_table_column` -> `check_column` -> `check_cell`. At each stage the checks relevant to that subset of the data are performed. So checks that are checking the properties of a column as a whole are found in `check_column` while checks that are checking something about an individual entry occur in `check_cell`.

## Summary

### Overview

The setup for creating the summary documents is more complicated than I would like but it fits the criteria for this project better than any other solution I could come up with. There are several stages involved in creating the final summary. It starts with `mmeds/summary.py`. This file contains functions that gather all the desired files after an analysis is run. It moves these files into a directory called `summary` in the root directory of the analysis being summarized. The functions then create a python notebook (extension `.ipynb`) in that directory. The code in the notebook is primarily taken from pre-written code blocks in `mmeds/resources/summary_code.txt`. These code blocks are a combination of R and Python that parse and create plots from the results of the analysis. The legends are generated separately however.

Before the final PDF is produced, the notebook will be executed and converted to latex using `jupyter nbconvert ...`. This conversion involves a template file (the original is found at `mmeds/resources/revtex.tplx`). This template is modified during the execution of the notebook. It is updated with the colors and values necessary for creating the legends. This information is then written into the latex version of the notebook. That `.tex` file is then converted to a PDF by executing `pdflatex {file}.tex` twice. Running the command twice is necessary for some of the template formatting to show up. I don't know why. If you can get clickable header links and legends to work without it feel free to change that.


### Notebook
