#!/bin/bash -l
echo "In $(pwd)"
export REPO_DIR=$(pwd)
echo "Running setup from ${REPO_DIR}"

full_install=false

# For RedHat
if $full_install; then
    sudo dnf install texlive texlive-adjustbox texlive-ulem texlive-upquote texlive-xcolor texlive-braket texlive-revtex;
fi

echo 'Make .modules';
if [ ! ~/.modules ]; then
    mkdir ~/.modules;
fi
if [ ! ~/.modules/modulefiles ]; then
    mkdir ~/.modules/modulefiles;
fi
sudo chown -R travis:travis ~/.modules

# Create the necessary conda environments
if [ ! -d ~/.modules/mmeds-stable ]; then
    echo "Create mmeds-stable environment";
    conda create --file spec-file.txt -p ~/.modules/mmeds-stable --yes --quiet --copy &>/dev/null;
    ln -sf ~/.modules/mmeds-stable ~/miniconda2/envs/mmeds-stable;
    source activate mmeds-stable;
    echo "Install R libraries";
    Rscript setup.R &> /dev/null;
    source deactivate;
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
