# MMEDS Ubuntu Setup Guide
## Clone MMEDS
Pick an install directory for MMEDS and clone it. Will be referred to as [install-dir]
`git clone https://github.com/clemente-lab/mmeds-meta/tree/master/mmeds`

Get mmeds secrets unencoded file from David and place in install-dir:\
`[install-dir]/mmeds/secrets.py`

Deactivate anaconda if it's running:\
`conda deactivate`

In the [install-dir] run MMEDs setup as root:\
`sudo python setup.py install`

## Apache setup
[Apache information and setup](https://ubuntu.com/tutorials/install-and-configure-apache#1-overview)

```
sudo cp [install-dir]/www_files/mmeds_ubuntu.conf /etc/apache2/sites-available
cd /etc/apache2/sites-available
sudo a2ensite mmeds.conf
sudo systemctl restart apache2
```

## Add required files to /var/www/
Create necessary folders if they don't already exist:
```
sudo mkdir /var/www/mmeds_server_data/
sudo mkdir /var/www/mmeds_server_data/test_files
sudo mkdir /var/www/mmeds_server_data/CherryPySession
```

copy files to /var/www/:
```
sudo cp [install-dir]/test* /var/www/mmeds_server_data/test_files
sudo cp [install-dir]/*.gz /var/www/mmeds_server_data/test_files
```

Create symbolic link:\
`ln -s [install-dir]/www_files/app.py /var/www/html/myapp.wsgi`
Test symbolic link:\
`readlink -f myapp.wsgi`

Finally, grant general permissions to /var/www\
`sudo chmod -R 777 ./`

## mysql setup:
[Follow install instructions](https://dev.mysql.com/doc/mysql-installation-excerpt/5.7/en/)
Run the following command:
```
mysql
source [install-dir]/setup.sql
exit
```

Create a root user with no password:\
[instructions here](https://www.digitalocean.com/community/tutorials/how-to-create-a-new-user-and-grant-permissions-in-mysql)

## MongoDB setup:
[follow install instructinos here](https://docs.mongodb.com/manual/installation/)

## Other installs:
Run the following commands to install necessary requirements:\
All packages need to be installed as root using sudo:\
`sudo apt-get update`

Install pip if you haven't already:\
[pip](https://linuxize.com/post/how-to-install-pip-on-ubuntu-20.04/)

```
sudo apt-get install libapache2-mod-wsgi-py3
sudo pip install psutil==5.7.3
sudo pip install more-itertools
sudo pip install jaraco.collections
sudo pip install zc.lockfile
sudo pip install cheroot
sudo pip install portend
sudo pip install CherryPy
sudo apt-get install python libexpat1
sudo apt-get install apache2 apache2-utils ssl-cert
```

## Start MMEDs
```
sudo systemctl start apache2
sudo systemctl start mongod
sudo systemctl start mysql
```

In MMEDs install directory:\
```
sudo python host/manager.py
```

Get your IP address and load the MMEDs webpage in your browser of preference:\
`ip addr show`
[ip-address]/myapp/

## Troubleshooting:
If the webpage isn't loading and/or an error is showing, check Apache2's error log for clues:\
`vi /var/log/apache2/error.log`

If you get permissions issues connecting to mysql, try adding the skip-grant-tables setting:\
[skip-grant-tables](https://superuser.com/questions/1127299/how-to-restart-mysql-with-skip-grant-tables-if-you-cant-use-the-root-password)

Make sure python3 is the default for your system:\
`python --version`\
[default python version](https://unix.stackexchange.com/questions/410579/change-the-python3-default-version-in-ubuntu)
[default python version2](https://dev.to/serhatteker/how-to-upgrade-to-python-3-7-on-ubuntu-18-04-18-10-5hab)
