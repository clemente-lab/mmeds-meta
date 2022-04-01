#!/bin/bash
#BSUB -q premium
#BSUB -W 6:00
#BSUB -J adamcantor22-Qiime2_0
#BSUB -P acc_MMEDS
#BSUB -n 10
#BSUB -R "span[hosts=1]"
#BSUB -R rusage[mem=10000]
#BSUB -o /sc/arion/projects/MMEDS/mmeds_server_data/studies/adamcantor22_Example_Study_0/Qiime2_0/adamcantor22-Qiime2_0.stdout
#BSUB -eo /sc/arion/projects/MMEDS/mmeds_server_data/studies/adamcantor22_Example_Study_0/Qiime2_0/adamcantor22-Qiime2_0.stderr
#BSUB -L /bin/bash

export QIIME_BSUB_OPTIONS='-q premium -P acc_MMEDS -W 2:00 -n 1 -R rusage[mem=2000]';
export PATH="~/usr/share/miniconda/bin:$PATH"

# conda init
# source ~/.bashrc;

set -e
set -o pipefail
echo $PATH
export LC_ALL=en_US.UTF-8;
# ml anaconda3;

#TODO: get conda env file for this:
# conda env create -f ./conda_env_files/qiime2-2020.8_env.yaml -p ~/conda_env_files/qiime2-2020.8 --force

#conda init bash

# conda activate /home/runner/conda_env_files/qiime2-2020.8;

test_files=~/mmeds_server_data/test_files
RUN_Qiime2=$test_files/test_study/Qiime2_0
import_dir=$RUN_Qiime2/import_dir

wait
echo "MMEDS_STAGE_5"
# conda deactivate; source activate jupyter; ml texlive/2018
python -m ipykernel install --user --name jupyter --display-name "Jupyter"
summarize.py  --path "$RUN_Qiime2" --tool_type qiime2;
zip -r $RUN_Qiime2.zip $RUN_Qiime2;
echo "MMEDS_FINISHED"
