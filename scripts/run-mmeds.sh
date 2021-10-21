#!/bin/bash

qiimedir=/sc/arion/projects/clemej05a/matt/mmeds/qiime-dir

forward=$qiimedir/xxx_S1_L001_R1_001.fastq
reverse=$qiimedir/xxx_S1_L001_R2_001.fastq
forwardbarcode=$qiimedir/xxx_S1_L001_I1_001.fastq
reversebarcode=$qiimedir/xxx_S1_L001_I2_001.fastq
map=$qiimedir/full_metadata.tsv

FSL=$(pwd)
outputdir=$FSL/outputs_mmeds

debug=$1
if [[ "$debug" = true ]]; then
    pudb='-m pudb '
else
    pudb=''
fi

cd /sc/arion/projects/clemej05a/matt/mmeds-meta

#source activate mmeds 
# source activate /hpc/users/stapym01/.conda/envs/mmeds
# python setup.py install --prefix /hpc/users/stapym01/.conda/envs/mmeds

python scripts/test-barcodes.py -f $forward -r $reverse -fb $forwardbarcode -rb $reversebarcode -m $map -o $outputdir

# python scripts/test-barcodes.py -f $forward -r $reverse -fb $forwardbarcode -rb $reversebarcode -m $map -o $outputdir
