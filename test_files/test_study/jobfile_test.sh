#!/bin/bash
#BSUB -q premium
#BSUB -W 6:00
#BSUB -J mattS-Qiime2_0
#BSUB -P acc_MMEDS
#BSUB -n 10
#BSUB -R "span[hosts=1]"
#BSUB -R rusage[mem=10000]
#BSUB -o /sc/arion/projects/MMEDS/mmeds_server_data/studies/mattS_Example_Study_test_0/Qiime2_0/mattS-Qiime2_0.stdout
#BSUB -eo /sc/arion/projects/MMEDS/mmeds_server_data/studies/mattS_Example_Study_test_0/Qiime2_0/mattS-Qiime2_0.stderr
#BSUB -L /bin/bash

export QIIME_BSUB_OPTIONS='-q premium -P acc_MMEDS -W 2:00 -n 1 -R rusage[mem=2000]';

#source ~/.bashrc;
set -e
set -o pipefail
echo $PATH
export LC_ALL=en_US.UTF-8;
#ml anaconda3;

test_files=~/mmeds_server_data/test_files
RUN_Qiime2=$test_files/test_study/Qiime2_0
import_dir=$RUN_Qiime2/import_dir

mkdir -p $RUN_Qiime2/import_dir
mkdir -p $RUN_Qiime2/temp

cp $test_files/forward_reads.fastq.gz $import_dir/sequences.fastq.gz
cp $test_files/barcodes.fastq.gz $import_dir

echo "MMEDS_STAGE_0"
qiime tools import --type EMPSingleEndSequences --input-path $RUN_Qiime2/import_dir --output-path $RUN_Qiime2/qiime_artifact.qza;
echo "MMEDS_STAGE_1"
qiime demux emp-single --i-seqs $RUN_Qiime2/qiime_artifact.qza --m-barcodes-file $RUN_Qiime2/qiime_mapping_file.tsv --m-barcodes-column BarcodeSequence --o-error-correction-details $RUN_Qiime2/error_correction.qza --o-per-sample-sequences $RUN_Qiime2/demux_file.qza;
qiime demux summarize --i-data $RUN_Qiime2/demux_file.qza --o-visualization $RUN_Qiime2/demux_viz.qzv;
qiime dada2 denoise-single --i-demultiplexed-seqs $RUN_Qiime2/demux_file.qza --p-trim-left 0 --p-trunc-len 0 --o-representative-sequences $RUN_Qiime2/rep_seqs_dada2.qza --o-table $RUN_Qiime2/table_dada2.qza --o-denoising-stats $RUN_Qiime2/stats_dada2.qza --p-n-threads 1;
qiime metadata tabulate --m-input-file $RUN_Qiime2/stats_dada2.qza --o-visualization $RUN_Qiime2/stats_dada2_visual.qzv;
echo "MMEDS_STAGE_2"
qiime feature-table filter-samples --i-table $RUN_Qiime2/table_dada2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-filtered-table $RUN_Qiime2/filtered_table.qza
qiime feature-table summarize --i-table $RUN_Qiime2/filtered_table.qza --o-visualization $RUN_Qiime2/filtered_viz.qzv
qiime alignment mafft --i-sequences $RUN_Qiime2/rep_seqs_dada2.qza --o-alignment $RUN_Qiime2/alignment.qza;
qiime alignment mask --i-alignment $RUN_Qiime2/alignment.qza --o-masked-alignment $RUN_Qiime2/masked_alignment.qza;
qiime phylogeny fasttree --i-alignment $RUN_Qiime2/masked_alignment.qza --o-tree $RUN_Qiime2/unrooted_tree.qza;
qiime phylogeny midpoint-root --i-tree $RUN_Qiime2/unrooted_tree.qza --o-rooted-tree $RUN_Qiime2/rooted_tree.qza;
qiime diversity core-metrics-phylogenetic --i-phylogeny $RUN_Qiime2/rooted_tree.qza --i-table $RUN_Qiime2/filtered_table.qza --p-sampling-depth 1000 --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-n-jobs-or-threads 1  --output-dir $RUN_Qiime2/core_metrics_results;
echo "MMEDS_STAGE_3"
qiime diversity alpha-group-significance --i-alpha-diversity $RUN_Qiime2/core_metrics_results/faith_pd_vector.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/faith_pd_group_significance.qzv&
qiime diversity alpha-group-significance --i-alpha-diversity $RUN_Qiime2/core_metrics_results/shannon_vector.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/shannon_group_significance.qzv&
qiime diversity alpha-group-significance --i-alpha-diversity $RUN_Qiime2/core_metrics_results/observed_features_vector.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/observed_features_group_significance.qzv&
qiime diversity alpha-group-significance --i-alpha-diversity $RUN_Qiime2/core_metrics_results/evenness_vector.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/evenness_group_significance.qzv&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenBodySite --o-visualization $RUN_Qiime2/unweighted_SpecimenBodySite_significance.qzv --p-pairwise&
qiime diversity alpha-rarefaction --i-table $RUN_Qiime2/filtered_table.qza --i-phylogeny $RUN_Qiime2/rooted_tree.qza --p-max-depth 4000 --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/alpha_rarefaction.qzv&
wait
echo "MMEDS_STAGE_4"
qiime feature-classifier classify-sklearn --i-classifier $test_files/gg-13-8-99-nb-2020-8-0.qza --i-reads $RUN_Qiime2/rep_seqs_dada2.qza --o-classification $RUN_Qiime2/taxonomy.qza --p-n-jobs 1
qiime taxa barplot --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/taxa_bar_plot.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenBodySite-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenBodySite-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenBodySite --o-visualization $RUN_Qiime2/ancom-SpecimenBodySite.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 6 --o-collapsed-table $RUN_Qiime2/SpecimenBodySite_table_l6.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenBodySite-table-l6.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenBodySite-table-l6.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenBodySite --o-visualization $RUN_Qiime2/ancom-SpecimenBodySite-l6.qzv

echo "MMEDS_STAGE_5"
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenBodySite --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SpecimenBodySite_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SpecimenBodySite_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SpecimenBodySite_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SpecimenBodySite_taxa_bar_plot.qzv
