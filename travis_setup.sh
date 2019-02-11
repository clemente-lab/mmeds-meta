#!/bin/bash -l
if [ ! -f ~/.install_log.txt ]; then
    touch ~/.install_log.txt;
fi

if [ ! -d ~/.local ]; then
    mkdir "$HOME/.local";
fi

if [ ! -d ~/.modules ]; then
    echo "Make .modules";
    mkdir ~/.modules
fi
if [ ! -d ~/.modules/modulefiles ]; then
    echo "make .modules/modules";
    mkdir ~/.modules/modulefiles
fi
if [ ! -f ~/.modules/modulefiles/qiime1 ]; then
    echo "Create qiime1 module";
    echo "#%Module1.0\n## qiime1 modulefile\nset curMod [module-info name]\nmodule-info name qiime1\nmodule-info version 1.9.1\nprepend-path PATH ~/.modules/qiime1/bin" > ~/.modules/modulefiles/qiime1
fi
if [ ! -f ~/.modules/modulefiles/qiime2 ]; then
    echo "Create qiime2 module";
    echo "#%Module1.0\n## qiime2 modulefile\nset curMod [module-info name]\nmodule-info name qiime2\nmodule-info version 2019.1\nprepend-path PATH ~/.modules/qiime2/bin" > ~/.modules/modulefiles/qiime2
fi
if [ ! -f ~/.modules/modulefiles/mmeds-stable ]; then
    echo "Create mmeds-stable module";
    echo "#%Module1.0\n## mmeds-stable modulefile\nset curMod [module-info name]\nmodule-info name mmeds-stable\nmodule-info version 1.5.1\nprepend-path PATH ~/miniconda2/envs/mmeds-stable/bin" > ~/.modules/modulefiles/mmeds-stable
fi
if [ ! -d ~/.modules/qiime1 ]; then
    echo "Create qiime1 environment"
    ls -a ~/.modules;
    conda create python=2.7 qiime matplotlib=1.4.3 mock nose -c bioconda --yes --quiet --copy -p ~/.modules/qiime1;
fi
if [ ! -d ~/.modules/qiime2 ]; then
    echo "Create qiime2 environment"
    wget https://data.qiime2.org/distro/core/qiime2-2019.1-py36-linux-conda.yml -O ~/qiime2.yml --quiet;
    ls -a ~/.modules;
    conda env create --file ~/qiime2.yml --quiet -p ~/.modules/qiime2;
fi

if [ ! -d ~/envmodule.tar.gz ]; then
    wget https://sourceforge.net/projects/modules/files/Modules/modules-4.2.1/modules-4.2.1.tar.gz -O ~/modules-4.2.1.tar.gz;
    cd;
    tar -zxf modules-4.2.1.tar.gz;
    echo "Unzipped"
    cd ~/modules-4.2.1;
    echo "In dir";
    ./configure --prefix="${HOME}/.local" --modulefilesdir="${HOME}/.modules/modulefiles";
    echo "configured"
    make &>/dev/null;
    echo "made"
    sudo make install;
    echo "installed"
    sudo make testinstall;
    export PATH="$HOME/.local/bin:$PATH"
    sudo ln -s "${HOME}/.local/init/profile.sh /etc/profile.d/modules.sh";
    sed -e "\$asource ~/.local/init/bash";
    source ~/.bashrc;
    sudo make testinstall;
    #yes | add.modules || echo "Okay";
    module use ~/.modules/modulefiles;
    module avail;
fi
