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

#### Additional Analysis
This is some functionality similar to that for creating sub-analyses but with some key differences. Where a sub-analysis runs the same tool (generally Qiime1 or Qiime2) on a subset on the data, an additional analysis is an analysis with a different tool performed on some data generated by the primary analysis. For example, a primary analysis of Qiime2 could have an additional analysis of SparCC, so that would automatically run SparCC on the OTU table generated during the Qiime2 run (ASV tables can bite me). As with Restarting analysis and Sub-analysis, ever since I stopped being able to maintain analysis tests as part of the automated testing suite I'm not sure if this works or not. The method `create_additional_analysis` shares a lot of code with `create_sub_analysis` but the differences were significant enough that I never managed to unify them. Also this stuff just stopped being a priority after the old nodes were retired and I had to move MMEDS to a WSGI app on HPC's apache setup.


### Qiime1

### Qiime2

## Summary

### Overview

The setup for creating the summary documents is more complicated than I would like but it fits the criteria for this project better than any other solution I could come up with. There are several stages involved in creating the final summary. It starts with `mmeds/summary.py`. This file contains functions that gather all the desired files after an analysis is run. It moves these files into a directory called `summary` in the root directory of the analysis being summarized. The functions then create a python notebook (extension `.ipynb`) in that directory. The code in the notebook is primarily taken from pre-written code blocks in `mmeds/resources/summary_code.txt`. These code blocks are a combination of R and Python that parse and create plots from the results of the analysis. The legends are generated separately however.

Before the final PDF is produced, the notebook will be executed and converted to latex using `jupyter nbconvert ...`. This conversion involves a template file (the original is found at `mmeds/resources/revtex.tplx`). This template is modified during the execution of the notebook. It is updated with the colors and values necessary for creating the legends. This information is then written into the latex version of the notebook. That `.tex` file is then converted to a PDF by executing `pdflatex {file}.tex` twice. Running the command twice is necessary for some of the template formatting to show up. I don't know why. If you can get clickable header links and legends to work without it feel free to change that.


### Notebook
