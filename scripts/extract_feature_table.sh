#!/bin/sh

# Unzip a .qza archive, convert its biom content into readable tsv format

in_file=$1
out_file=$2
file_type="${3:-tsv}" # tsv, biom, or fasta
tmp_dir_name="${4:-tmp_unzip}"
unzip -joq $in_file -d $tmp_dir_name

if [[ "$file_type" == "tsv" ]]; then
    biom convert --to-tsv -i $tmp_dir_name/feature-table.biom -o $out_file
    sed -i '1d;2s/^#//' $out_file
    rm -rf $tmp_dir_name
elif [[ "$file_type" == "biom" ]]; then
    cp $tmp_dir_name/feature-table.biom $out_file
    rm -rf $tmp_dir_name
elif [[ "$file_type" == "fasta" ]]; then
    cp $tmp_dir_name/dna-sequences.fasta $out_file
    rm -rf $tmp_dir_name
else
    echo "Invalid file_type argument"
fi

