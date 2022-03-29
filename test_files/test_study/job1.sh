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

echo "hi"
export QIIME_BSUB_OPTIONS='-q premium -P acc_MMEDS -W 2:00 -n 1 -R rusage[mem=2000]';

source ~/.bashrc;

set -e
set -o pipefail
echo $PATH
export LC_ALL=en_US.UTF-8;
# ml anaconda3;

test_files=~/mmeds_server_data/test_files
RUN_Qiime2=$test_files/test_study/Qiime2_0
import_dir=$RUN_Qiime2/import_dir

cp $test_files/forward_reads.fastq.gz $import_dir/sequences.fastq.gz
cp $test_files/qiime_mapping_file.tsv $RUN_Qiime2/
# cp $test_files/reverse_reads.fastq.gz $import_dir
cp $test_files/barcodes.fastq.gz $import_dir

echo "MMEDS_STAGE_0"
qiime tools import --type EMPSingleEndSequences --input-path $RUN_Qiime2/import_dir --output-path $RUN_Qiime2/qiime_artifact.qza;
echo "MMEDS_STAGE_1"
# qiime demux emp-single --i-seqs $RUN_Qiime2/qiime_artifact.qza --m-barcodes-file $RUN_Qiime2/qiime_mapping_file.tsv --m-barcodes-column BarcodeSequence --o-error-correction-details $RUN_Qiime2/error_correction.qza --o-per-sample-sequences $RUN_Qiime2/demux_file.qza;
