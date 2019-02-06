#!/usr/bin/bash

if [ ! -d ~/.modules ]; then
    mkdir ~/.modules
fi
if [ ! -d ~/.modules/modulefiles ]; then
    mkdir ~/.modules/modulefiles
fi
if [! -f "~/.modules/modulefiles/qiime1" ]; then
    echo "#%Module1.0\n## qiime1 modulefile\nset curMod [module-info name]\nmodule-info name qiime1\nmodule-info version 1.9.1\nprepend-path PATH ~/.modules/qiime1/bin" > ~/.modules/modulefiles/qiime1
fi
if [! -f "~/.modules/modulefiles/qiime2" ]; then
    echo "#%Module1.0\n## qiime2 modulefile\nset curMod [module-info name]\nmodule-info name qiime2\nmodule-info version 2019.1\nprepend-path PATH ~/.modules/qiime2/bin" > ~/.modules/modulefiles/qiime2
fi
if [! -f "~/.modules/modulefiles/mmeds-stable" ]; then
    echo "#%Module1.0\n## mmeds-stable modulefile\nset curMod [module-info name]\nmodule-info name mmeds-stable\nmodule-info version 1.5.1\nprepend-path PATH ~/miniconda2/envs/mmeds-stable/bin" > ~/.modules/modulefiles/mmeds-stable
fi
if [! -d ~/.modules/qiime1]; then
    conda create python=2.7 qiime matplotlib=1.4.3 mock nose -c bioconda --yes --quiet --copy -p ~/.modules/qiime1 &>> install_log.txt;
fi
if [! -d ~/.modules/qiime2]; then
    wget https://data.qiime2.org/distro/core/qiime2-2019.1-py36-linux-conda.yml -O ~/qiime2.yml --quiet
    conda env create --file ~/qiime2.yml --quiet --copy -p ~/.modules/qiime2 &>> install_log.txt;
fi
