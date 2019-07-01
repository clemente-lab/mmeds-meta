#!/bin/bash -l
echo "In $(pwd)"
export REPO_DIR=$(pwd)
echo "Running setup from ${REPO_DIR}"

# Anaconda setup
wget http://repo.continuum.io/miniconda/Miniconda-latest-Linux-x86_64.sh -O ~/miniconda.sh --quiet;
chmod +x ~/miniconda.sh;
~/miniconda.sh -b;
export PATH=~/miniconda2/bin:$PATH;
conda update --yes conda;

echo 'Make .modules';
mkdir ~/.modules;
echo 'Make .modules/modulefiles';
mkdir ~/.modules/modulefiles;

# Create the necessary conda environments
echo "Create mmeds-stable environment";
conda create --file spec-file.txt -p ~/.modules/mmeds-stable --yes --quiet --copy;
ln -sf ~/.modules/mmeds-stable ~/miniconda2/envs/mmeds-stable;
source activate mmeds-stable;
echo "Install R libraries";
Rscript setup.R;
source deactivate;

echo "Create qiime1 environment";
conda create python=2.7 qiime matplotlib=1.4.3 mock nose -c bioconda --yes --quiet --copy -p ~/.modules/qiime1;
echo "Create qiime2 environment"
wget https://data.qiime2.org/distro/core/qiime2-2019.1-py36-linux-conda.yml -O ~/qiime2.yml --quiet;
conda env create --file ~/qiime2.yml --quiet -p ~/.modules/qiime2;

# Configure and install environment modules
echo "Install environment-modules";
wget https://sourceforge.net/projects/modules/files/Modules/modules-4.2.1/modules-4.2.1.tar.gz -O modules-4.2.1.tar.gz &>/dev/null;
tar -zxf modules-4.2.1.tar.gz;
cd modules-4.2.1;
./configure --prefix="${HOME}/.local" --modulefilesdir="${HOME}/.modules/modulefiles" #&>/dev/null;
make;
sudo make install;
cd $REPO_DIR;

# Make sure module will work
export PATH="$HOME/.local/bin:$PATH"
sudo ln -s "${HOME}/.local/init/profile.sh /etc/profile.d/modules.sh";
sed -i "\$asource ${HOME}/.local/init/bash" ~/.bashrc;

# Create links to the conda envs
ln -sf ~/.modules/qiime1 ~/miniconda2/envs/qiime1;
ln -sf ~/.modules/qiime2 ~/miniconda2/envs/qiime2;
ln -sf ~/.modules/mmeds-stable ~/miniconda2/envs/mmeds-stable;

# Create links to the module files
# TEMPORARY
rm -rf ~/.modules/modulefiles/qiime1
rm -rf ~/.modules/modulefiles/qiime2
mkdir ~/.modules/modulefiles/qiime
mkdir ~/.modules/modulefiles/qiime2
ln -sf $REPO_DIR/modules/mmeds-stable ~/.modules/modulefiles/mmeds-stable
ln -sf $REPO_DIR/modules/qiime2 ~/.modules/modulefiles/qiime2/2019.1
ln -sf $REPO_DIR/modules/qiime1 ~/.modules/modulefiles/qiime/1.9.1

cd $REPO_DIR;
echo "Finished setup. In $(pwd)"
