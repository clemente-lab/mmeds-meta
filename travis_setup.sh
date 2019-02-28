#!/bin/bash -l
echo "In $(pwd)"
export REPO_DIR=$(pwd)
echo "Running setup from ${REPO_DIR}"

# Install libtidy because package is super old
git clone https://github.com/htacg/tidy-html5;
cd tidy-html5/build/cmake;
cmake ../.. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr;
make;
sudo make install;
cd ../../..;


if [ ! -d ~/.modules ]; then
    echo 'Make .modules';
    mkdir ~/.modules;
    mkdir ~/.modules/modulefiles;
    sudo chown -R travis:travis ~/.modules
fi

# Create module files (and install R packages)
if [ ! -f ~/.modules/modulefiles/qiime1 ]; then
    echo "Create qiime1 module";
    printf "#%%Module1.0\n## qiime1 modulefile\nset curMod [module-info name]\nmodule-info name qiime1\nmodule-info version 1.9.1\nprepend-path PATH ~/.modules/qiime1/bin\nif [ module-info mode load ] {\nputs stderr \"~/.modules/qiime1/bin\"\n}" > ~/.modules/modulefiles/qiime1
fi
#if [ ! -f ~/.modules/modulefiles/qiime2 ]; then
#    echo "Create qiime2 module";
#    printf "#%%Module1.0\n## qiime2 modulefile\nset curMod [module-info name]\nmodule-info name qiime2\nmodule-info version 2019.1\nprepend-path PATH ~/.modules/qiime2/bin" > ~/.modules/modulefiles/qiime2
#fi
if [ ! -f ~/.modules/modulefiles/mmeds-stable ]; then
    echo "Create mmeds-stable module";
    printf "#%%Module1.0\n## mmeds-stable modulefile\nset curMod [module-info name]\nmodule-info name mmeds-stable\nmodule-info version 1.5.1\nprepend-path PATH ~/.modules/mmeds-stable/bin\nif [ module-info mode load ] {\nputs stderr \"~/.modules/mmeds-stable/bin\"\n}" > ~/.modules/modulefiles/mmeds-stable
fi

# Create the necessary conda environments
if [ ! -d ~/.modules/mmeds-stable ]; then
    echo "Create mmeds-stable environment";
    conda create --file spec-file.txt -p ~/.modules/mmeds-stable --yes --quiet --copy &>/dev/null;
    ln -sf ~/.modules/mmeds-stable ~/miniconda2/envs/mmeds-stable;
    source activate mmeds-stable;
    echo "Install R libraries";
    Rscript setup.R;
    source deactivate;
fi
if [ ! -d ~/.modules/qiime1 ]; then
    echo "Create qiime1 environment";
    conda create python=2.7 qiime matplotlib=1.4.3 mock nose -c bioconda --yes --quiet --copy -p ~/.modules/qiime1 &>/dev/null;
fi

# Configure and install environment modules
if [ ! -d ~/.local ]; then
    echo "Install environment-modules";
    wget https://sourceforge.net/projects/modules/files/Modules/modules-4.2.1/modules-4.2.1.tar.gz -O modules-4.2.1.tar.gz &>/dev/null;
    tar -zxf modules-4.2.1.tar.gz;
    cd modules-4.2.1;
    ./configure --prefix="${HOME}/.local" --modulefilesdir="${HOME}/.modules/modulefiles" &>/dev/null;
    make &>/dev/null;
    sudo make install &>/dev/null;
    cd $REPO_DIR;
fi

# Make sure module will work
export PATH="$HOME/.local/bin:$PATH"
sudo ln -s "${HOME}/.local/init/profile.sh /etc/profile.d/modules.sh";
sed -i "\$asource ${HOME}/.local/init/bash" ~/.bashrc;

#if [ ! -d ~/.modules/qiime2 ]; then
#    echo "Create qiime2 environment"
#    wget https://data.qiime2.org/distro/core/qiime2-2019.1-py36-linux-conda.yml -O ~/qiime2.yml --quiet;
#    conda env create --file ~/qiime2.yml --quiet -p ~/.modules/qiime2 &>/dev/null;
#fi

# Create links
ln -sf ~/.modules/qiime1 ~/miniconda2/envs/qiime1;
ln -sf ~/.modules/qiime2 ~/miniconda2/envs/qiime2;
ln -sf ~/.modules/mmeds-stable ~/miniconda2/envs/mmeds-stable;

cd $REPO_DIR;
echo "Finished setup. In $(pwd)"
