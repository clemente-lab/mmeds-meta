# mmeds-meta

### Instructions

In order to run the mmeds server locally you will need.

- Some mysql server running on your machine. For development we are using mariadb.
To install on linux install the `mariadb` and `mariadb-server` packages using your distro's manager.
For other OS's the installer can be found here  
https://downloads.mariadb.org/


- A mongoDB server running on your machine. Installers can be found at the following link.  
https://www.mongodb.com/download-center#community 


To setup the SQL database run the following scripts in this order:  
    1. sql/tables.sql  
    2. sql/functions.sql  
    3. sql/users.sql  
    4. sql/views.sql  


Run `python setup.py install` to install the necessary dependencies.

To start the server change to the server directory and run `python server.py`
