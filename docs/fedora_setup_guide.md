# INFO
# https://docs.fedoraproject.org/en-US/Fedora/12/html/Deployment_Guide/s1-apache-addmods.html


```
MMEDS="/mmeds/install/location"
```

# Install python and apache
```
sudo dnf install python3 python3-devel httpd httpd-devel -y;
cd ~/Downloads;
```

# Get mod_wsgi

```
wget https://github.com/GrahamDumpleton/mod_wsgi/archive/4.7.1.tar.gz;
tar -zxvf ~/Downloads/mod_wsgi-4.7.1.tar.gz;
sudo mv ~/Downloads/mod_wsgi-4.7.1 /opt/.;
cd /opt/mod_wsgi-4.7.1;
```



# Build mod_wsgi
```
./configure;
make;
sudo make install;
```


# Add module to apache
`sudo $(echo "LoadModule wsgi_module modules/mod_wsgi.so" &> /etc/httpd/conf.modules.d/00-wsgi.conf)`

# Add virtual environment setup
`sudo $(cat $MMEDS/vhost.conf &> /etc/httpd/conf.d/wsgi.conf)`

# Set apache to run as me (david/user account)
#
# Modify cherrypy to use File System based sessions
#
# To set SELinux to allow apache to do things with files
# chcon -R -t httpd_sys_rw_content_t /path/to/dir
#
# With one daemon thread I'm not seeing the session logout issues. I think that is why the resets are happening
# But why is that an issue for the non-daemon version. It wasn't working even with the filesystem sessions


apachectl restart

# Fix SELinux
`sudo setsebool -P httpd_read_user_content 1`

# Disable selinux
`sudo setenforce 0`


## App Root
`/usr/local/www/wsgi-scripts`
