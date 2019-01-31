# mmeds-meta



#### Master
[![codecov](https://codecov.io/gh/clemente-lab/mmeds-meta/branch/master/graph/badge.svg)](https://codecov.io/gh/clemente-lab/mmeds-meta)

#### Development
[![codecov](https://codecov.io/gh/clemente-lab/mmeds-meta/branch/development/graph/badge.svg)](https://codecov.io/gh/clemente-lab/mmeds-meta)



## Instructions

In order to run the mmeds server locally you will need.

- Some mysql server running on your machine. For development we are using mariadb.
To install on linux install the `mariadb` and `mariadb-server` packages using your distro's manager.
For other OS's the installer can be found here  
https://downloads.mariadb.org/


- A mongoDB server running on your machine. Installers can be found at the following link.  
https://www.mongodb.com/download-center#community 


To setup the SQL database connect to you sql database as root:  
`mysql -u root`  
Then run the following command.  
    `source setup.sql;`  

mmeds is written in in Python3 so you will need a python3 environment to run it.
Run `python setup.py install` to install the necessary dependencies.

To start the server change to the server directory and run `python server.py 1`

To connect to the server go to https://localhost:8080
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

latex_template: https://michaelgoerz.net/notes/custom-template-for-converting-jupyter-notebooks-to-latex.html
