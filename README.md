# mmeds-meta

### Instructions

In order to run the mmeds server locally you will need.

- Some mysql server running on your machine. For development we are using mariadb.

- A mongoDB server running on your machine.


To setup the SQL database run the following scripts in this order:
    1) sql/tables.sql
    2) sql/functions.sql
    3) sql/users.sql
    4) sql/views.sql


Run `python setup.py install` to install the necessary dependencies.

To start the server change to the server directory and run `python server.py`
