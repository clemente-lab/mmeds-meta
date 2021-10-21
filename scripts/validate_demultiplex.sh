#!/bin/bash
#BSUB -q premium
#BSUB -W 6:00
#BSUB -J adamcantor22-Qiime2_1
#BSUB -P acc_MMEDS
#BSUB -n 10
#BSUB -R "span[hosts=1]"
#BSUB -R rusage[mem=1000]
#BSUB -o /sc/arion/projects/MMEDS/mmeds_server_data/studies/adamcantor22_All_Comer_Bladder_Cancer_Patients_3_0/Qiime2_1/adamcantor22-Qiime2_1.stdout
#BSUB -eo /sc/arion/projects/MMEDS/mmeds_server_data/studies/adamcantor22_All_Comer_Bladder_Cancer_Patients_3_0/Qiime2_1/adamcantor22-Qiime2_1.stderr
#BSUB -L /bin/bash

basedir=/sc/arion/projects/clemej05a/matt/mmeds/qiime-dir
RUN_Qiime2=/sc/arion/projects/clemej05a/matt/mmeds/qiime-dir/Qiime2_validate_demultiplex

# ml purge

# extract barcodes code
module load anaconda2
# source activate qiime1.9.1
source activate /hpc/users/stapym01/.conda/envs/qiime1.9.1
module load python/2.7.9-UCS4

# gunzip data/240_16_CTCGACTTATCGTACG_L001_R1_001.fastq.gz
#sed -n '1~4s/^@/>/p;2~4p' data/240_16_CTCGACTTATCGTACG_L001_R1_001.fastq > data/240_16.fasta
# validate_mapping_file.py -m qiime_mapping_file_test.tsv
#validate_demultiplexed_fasta.py -i data/240_16.fasta -m qiime_mapping_file.tsv -o validate_output -b

# validate_demultiplexed_fasta.py -i data/240_16_L001_R1_001.fasta -m qiime_mapping_file.tsv -o validate_output
# validate_demultiplexed_fasta.py -i data/240_16_L001_R1_001.fasta -m qiime_mapping_file.tsv -o validate_output -b -a 
validate_demultiplexed_fasta.py -i data/240_16_L001_R1_001.fasta -m qiime_mapping_file_test.tsv -o validate_output -b -a 



# validate_demultiplexed_fasta.py -i data/240_16_CTCGACTTATCGTACG_L001_R1_001.fastq -m qiime_mapping_file.tsv -o validate_output -b



# conda deactivate
