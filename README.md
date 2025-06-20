# mmeds-meta

[![Tests Passing](https://github.com/clemente-lab/mmeds-meta/actions/workflows/tests.yml/badge.svg)](https://github.com/clemente-lab/mmeds-meta/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/clemente-lab/mmeds-meta/branch/master/graph/badge.svg)](https://codecov.io/gh/clemente-lab/mmeds-meta)
[![CodeFactor](https://www.codefactor.io/repository/github/clemente-lab/mmeds-meta/badge)](https://www.codefactor.io/repository/github/clemente-lab/mmeds-meta)

![MMEDS Image](/test_files/MMEDS_image.png?raw=true "MMEDs Server")

## Instructions

In order to run the mmeds server locally you will need.

-   Some mysql server running on your machine. For development we are using mariadb.
To install on linux install the `mariadb` and `mariadb-server` packages using your distro's manager.
For other OS's the installer can be found [here](https://downloads.mariadb.org)


-   A mongoDB server running on your machine. Installers can be found [here](https://www.mongodb.com/download-center#community)

To setup the SQL database connect to you sql database as root:  
`mysql -u root`  
Then run the following command.  
    `source setup.sql;`  

mmeds is written in in Python3 so you will need a python3 environment to run it.
Run `python setup.py install` to install the necessary dependencies.

To start the server change to the host directory and run `python host.py 1`

To connect to the server go to [MMEDS](https://localhost:52953)
Allow access to the webpage despite your browsers warning. The security certificate is not signed.

NOTE: Certain versions of openssl as installed by conda cause issues with cherrypy ssl. 
To fix this run `conda install openssl=1.0.2p`. This version should work.

The directory that uploads are saved in are determined by the value of
the `MMEDS` environment variable. If this variable is not set it defaults
to the current user's home directory.

Latex Dependencies  
adjustbox  
upquote  
ulem  
revtex  
braket  

Other Dependencies  
rpy2: 2.9.1  
readline headers  
jupyter_contrib_nbextensions  

[latex_template](https://michaelgoerz.net/notes/custom-template-for-converting-jupyter-notebooks-to-latex.html)

[font](https://www.1001fonts.com/code-new-roman-font.html)

If you encounter INVALID DISPLAY VARIABLE add the line `backend: agg` to your matplotlibrc
(typically ~/.config/matplotlib/matploblibrc)
or setup your environment with `export MPLBACKEND="agg"`

To install Qiime1.9.1 with a recent version of conda run:
`conda config --set allow_conda_downgrades true`  
`conda install conda=4.6.14`  
Prior to running the conda command for installing Qiime
