# INFO
# https://docs.fedoraproject.org/en-US/Fedora/12/html/Deployment_Guide/s1-apache-addmods.html


MMEDS="/mmeds/install/location"

if [ $0 == "fedora" ];
    # Install python and apache
    sudo dnf install python3 python3-devel httpd httpd-devel -y;
    cd ~/Downloads;

    # Get mod_wsgi
    wget https://github.com/GrahamDumpleton/mod_wsgi/archive/4.7.1.tar.gz;
    tar -zxvf ~/Downloads/mod_wsgi-4.7.1.tar.gz;
    sudo mv ~/Downloads/mod_wsgi-4.7.1 /opt/.;
    cd /opt/mod_wsgi-4.7.1;

    # Build mod_wsgi
    ./configure;
    make;
    sudo make install;

    # Add module to apache
    sudo $(echo "LoadModule wsgi_module modules/mod_wsgi.so" &> /etc/httpd/conf.modules.d/00-wsgi.conf)

    # Add virtual environment setup
    sudo $(cat $MMEDS/vhost.conf &> /etc/httpd/conf.d/wsgi.conf)


    apachectl restart

fi
