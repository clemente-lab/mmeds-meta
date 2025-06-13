#!/bin/sh

# Unzip a .qza archive, convert its biom content into readable tsv format

in_file=$1
out_file=$2
tmp_dir_name="${3:-tmp_unzip}"
unzip -joq $in_file -d $tmp_dir_name
biom convert --to-tsv -i $tmp_dir_name/feature-table.biom -o $out_file
sed -i '1d;2s/^#//' $out_file
rm -rf $tmp_dir_name
