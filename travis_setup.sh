#!/bin/bash -l
echo "In $(pwd)"
export REPO_DIR=$(pwd)
echo "Running setup from ${REPO_DIR}"

TRAVIS_HOME=$HOME
full_install=false

# For RedHat
if $full_install; then
    sudo dnf install texlive texlive-adjustbox texlive-ulem texlive-upquote texlive-xcolor texlive-braket texlive-revtex;
fi

# Install libtidy because package is super old
git clone https://github.com/htacg/tidy-html5;
cd tidy-html5/build/cmake;
cmake ../.. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr;
make;
sudo make install &> /dev/null;
cd ../../..;


echo 'Make .modules';
if [ ! ~/.modules ]; then
    mkdir ~/.modules;
fi
if [ ! ~/.modules/modulefiles ]; then
    mkdir ~/.modules/modulefiles;
fi
sudo chown -R travis:travis $TRAVIS_HOME/.modules

# Create the necessary conda environments
if [ ! -d ~/.modules/mmeds-stable ]; then
    echo "Create mmeds-stable environment";
    conda env create -f $REPO_DIR/environment.yml -p ~/.modules/mmeds-stable --quiet;
    ln -sf ~/.modules/mmeds-stable ~/miniconda2/envs/mmeds-stable;
fi

if false; then
    if [ ! -d ~/.modules/qiime1 ]; then
        echo "Create qiime1 environment";
        conda config --set restore_free_channel true
        conda create python=2.7 qiime matplotlib=1.4.3 mock nose -c bioconda --yes --quiet --copy -p ~/.modules/qiime1 &>/dev/null;
        conda config --set restore_free_channel false
    fi

    if [ ! -d ~/.modules/qiime2 ]; then
        echo "Create qiime2 environment"
        # Old Qiime2 version
        # wget https://data.qiime2.org/distro/core/qiime2-2019.1-py36-linux-conda.yml -O ~/qiime2.yml --quiet;
        wget https://data.qiime2.org/distro/core/qiime2-2019.7-py36-linux-conda.yml -O ~/qiime2.yml --quiet;
        conda env create --file ~/qiime2.yml --quiet -p ~/.modules/qiime2;
    fi
fi

if [ ! -f ~/.local/init/profile.sh ]; then
    # Configure and install environment modules
    sudo chown -R travis:travis $TRAVIS_HOME/.local
    mkdir ~/.local
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

# Create links to the conda envs
ln -sf ~/.modules/qiime1 ~/miniconda2/envs/qiime1;
ln -sf ~/.modules/qiime2 ~/miniconda2/envs/qiime2;
ln -sf ~/.modules/mmeds-stable ~/miniconda2/envs/mmeds-stable;

# Create links to the module files
if [ ! -d ~/.modules/modulefiles/qiime ]; then
    mkdir ~/.modules/modulefiles/qiime
fi
if [ ! -d ~/.modules/modulefiles/qiime2 ]; then
    mkdir ~/.modules/modulefiles/qiime2
fi
ln -sf $REPO_DIR/modules/mmeds-stable ~/.modules/modulefiles/mmeds-stable
ln -sf $REPO_DIR/modules/qiime2 ~/.modules/modulefiles/qiime2/2019.7
ln -sf $REPO_DIR/modules/qiime1 ~/.modules/modulefiles/qiime/1.9.1

cd $REPO_DIR;
echo "Finished setup. In $(pwd)"
