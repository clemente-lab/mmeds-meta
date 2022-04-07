#!/bin/bash
#BSUB -q premium
#BSUB -W 6:00
#BSUB -J mattS-Qiime2_0
#BSUB -P acc_MMEDS
#BSUB -n 10
#BSUB -R "span[hosts=1]"
#BSUB -R rusage[mem=10000]
#BSUB -o /sc/arion/projects/MMEDS/mmeds_server_data/studies/mattS_Example_Study3_0/Qiime2_0/mattS-Qiime2_0.stdout
#BSUB -eo /sc/arion/projects/MMEDS/mmeds_server_data/studies/mattS_Example_Study3_0/Qiime2_0/mattS-Qiime2_0.stderr
#BSUB -L /bin/bash

export QIIME_BSUB_OPTIONS='-q premium -P acc_MMEDS -W 2:00 -n 1 -R rusage[mem=2000]';

set -e
set -o pipefail
echo $PATH
export LC_ALL=en_US.UTF-8;

# ml anaconda3;
test_files=~/mmeds_server_data/test_files
RUN_Qiime2=$test_files/test_study/Qiime2_0
import_dir=$RUN_Qiime2/import_dir

# rm $import_dir/*

qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenBodySite --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SpecimenBodySite_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SpecimenBodySite_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SpecimenBodySite_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SpecimenBodySite_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Nationality --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_Nationality_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_Nationality_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_Nationality_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_Nationality_taxa_bar_plot.qzv
