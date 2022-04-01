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

# source ~/.bashrc;

set -e
set -o pipefail
echo $PATH
export LC_ALL=en_US.UTF-8;

# ml anaconda3;
# source activate qiime2-2020.8

test_files=~/mmeds_server_data/test_files
RUN_Qiime2=$test_files/test_study/Qiime2_0
import_dir=$RUN_Qiime2/import_dir

mkdir $RUN_Qiime2
mkdir $import_dir

# rm $import_dir/*
cp $test_files/forward_reads.fastq.gz $import_dir
mv $import_dir/forward_reads.fastq.gz $import_dir/sequences.fastq.gz

cp $test_files/qiime_mapping_file.tsv $RUN_Qiime2/
# cp $test_files/reverse_reads.fastq.gz $import_dir
cp $test_files/barcodes.fastq.gz $import_dir

echo "MMEDS_STAGE_0"
qiime tools import --type EMPSingleEndSequences --input-path $RUN_Qiime2/import_dir --output-path $RUN_Qiime2/qiime_artifact.qza;
echo "MMEDS_STAGE_1"
qiime demux emp-single --i-seqs $RUN_Qiime2/qiime_artifact.qza --m-barcodes-file $RUN_Qiime2/qiime_mapping_file.tsv --m-barcodes-column BarcodeSequence --o-error-correction-details $RUN_Qiime2/error_correction.qza --o-per-sample-sequences $RUN_Qiime2/demux_file.qza;
qiime demux summarize --i-data $RUN_Qiime2/demux_file.qza --o-visualization $RUN_Qiime2/demux_viz.qzv;
qiime dada2 denoise-single --i-demultiplexed-seqs $RUN_Qiime2/demux_file.qza --p-trim-left 0 --p-trunc-len 0 --o-representative-sequences $RUN_Qiime2/rep_seqs_dada2.qza --o-table $RUN_Qiime2/table_dada2.qza --o-denoising-stats $RUN_Qiime2/stats_dada2.qza --p-n-threads 10;
qiime metadata tabulate --m-input-file $RUN_Qiime2/stats_dada2.qza --o-visualization $RUN_Qiime2/stats_dada2_visual.qzv;
echo "MMEDS_STAGE_2"
qiime feature-table filter-samples --i-table $RUN_Qiime2/table_dada2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-filtered-table $RUN_Qiime2/filtered_table.qza
qiime feature-table summarize --i-table $RUN_Qiime2/filtered_table.qza --o-visualization $RUN_Qiime2/filtered_viz.qzv
qiime alignment mafft --i-sequences $RUN_Qiime2/rep_seqs_dada2.qza --o-alignment $RUN_Qiime2/alignment.qza;
qiime alignment mask --i-alignment $RUN_Qiime2/alignment.qza --o-masked-alignment $RUN_Qiime2/masked_alignment.qza;
qiime phylogeny fasttree --i-alignment $RUN_Qiime2/masked_alignment.qza --o-tree $RUN_Qiime2/unrooted_tree.qza;
qiime phylogeny midpoint-root --i-tree $RUN_Qiime2/unrooted_tree.qza --o-rooted-tree $RUN_Qiime2/rooted_tree.qza;
qiime diversity core-metrics-phylogenetic --i-phylogeny $RUN_Qiime2/rooted_tree.qza --i-table $RUN_Qiime2/filtered_table.qza --p-sampling-depth 1114 --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-n-jobs-or-threads 10  --output-dir $RUN_Qiime2/core_metrics_results;
echo "MMEDS_STAGE_3"
qiime diversity alpha-group-significance --i-alpha-diversity $RUN_Qiime2/core_metrics_results/faith_pd_vector.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/faith_pd_group_significance.qzv&
qiime diversity alpha-group-significance --i-alpha-diversity $RUN_Qiime2/core_metrics_results/shannon_vector.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/shannon_group_significance.qzv&
qiime diversity alpha-group-significance --i-alpha-diversity $RUN_Qiime2/core_metrics_results/observed_features_vector.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/observed_features_group_significance.qzv&
qiime diversity alpha-group-significance --i-alpha-diversity $RUN_Qiime2/core_metrics_results/evenness_vector.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/evenness_group_significance.qzv&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ExampleMetaData --o-visualization $RUN_Qiime2/unweighted_ExampleMetaData_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column AliquotID --o-visualization $RUN_Qiime2/unweighted_AliquotID_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenBodySite --o-visualization $RUN_Qiime2/unweighted_SpecimenBodySite_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column UberonCodeBodySite --o-visualization $RUN_Qiime2/unweighted_UberonCodeBodySite_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Biome --o-visualization $RUN_Qiime2/unweighted_Biome_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Ethnicity --o-visualization $RUN_Qiime2/unweighted_Ethnicity_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Genotype --o-visualization $RUN_Qiime2/unweighted_Genotype_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column HeightDateCollected --o-visualization $RUN_Qiime2/unweighted_HeightDateCollected_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ICDCode --o-visualization $RUN_Qiime2/unweighted_ICDCode_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessEndDate --o-visualization $RUN_Qiime2/unweighted_IllnessEndDate_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessNotes --o-visualization $RUN_Qiime2/unweighted_IllnessNotes_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessStartDate --o-visualization $RUN_Qiime2/unweighted_IllnessStartDate_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionEndDate --o-visualization $RUN_Qiime2/unweighted_InterventionEndDate_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionNotes --o-visualization $RUN_Qiime2/unweighted_InterventionNotes_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionStartDate --o-visualization $RUN_Qiime2/unweighted_InterventionStartDate_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionCode --o-visualization $RUN_Qiime2/unweighted_InterventionCode_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionName --o-visualization $RUN_Qiime2/unweighted_InterventionName_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column BarcodeSequence --o-visualization $RUN_Qiime2/unweighted_BarcodeSequence_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataID --o-visualization $RUN_Qiime2/unweighted_RawDataID_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataNotes --o-visualization $RUN_Qiime2/unweighted_RawDataNotes_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataDatePerformed --o-visualization $RUN_Qiime2/unweighted_RawDataDatePerformed_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataProtocolID --o-visualization $RUN_Qiime2/unweighted_RawDataProtocolID_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column TargetGene --o-visualization $RUN_Qiime2/unweighted_TargetGene_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultID --o-visualization $RUN_Qiime2/unweighted_ResultID_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsDatePerformed --o-visualization $RUN_Qiime2/unweighted_ResultsDatePerformed_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsProtocolID --o-visualization $RUN_Qiime2/unweighted_ResultsProtocolID_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsMethod --o-visualization $RUN_Qiime2/unweighted_ResultsMethod_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleID --o-visualization $RUN_Qiime2/unweighted_SampleID_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleDatePerformed --o-visualization $RUN_Qiime2/unweighted_SampleDatePerformed_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleProtocolID --o-visualization $RUN_Qiime2/unweighted_SampleProtocolID_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleToolVersion --o-visualization $RUN_Qiime2/unweighted_SampleToolVersion_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenCollectionDate --o-visualization $RUN_Qiime2/unweighted_SpecimenCollectionDate_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenCollectionTime --o-visualization $RUN_Qiime2/unweighted_SpecimenCollectionTime_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenID --o-visualization $RUN_Qiime2/unweighted_SpecimenID_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column StorageFreezer --o-visualization $RUN_Qiime2/unweighted_StorageFreezer_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Nationality --o-visualization $RUN_Qiime2/unweighted_Nationality_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Sex --o-visualization $RUN_Qiime2/unweighted_Sex_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenType --o-visualization $RUN_Qiime2/unweighted_SpecimenType_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column UberonCodeType --o-visualization $RUN_Qiime2/unweighted_UberonCodeType_significance.qzv --p-pairwise&
qiime diversity beta-group-significance --i-distance-matrix $RUN_Qiime2/core_metrics_results/unweighted_unifrac_distance_matrix.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column WeightDateCollected --o-visualization $RUN_Qiime2/unweighted_WeightDateCollected_significance.qzv --p-pairwise&
qiime diversity alpha-rarefaction --i-table $RUN_Qiime2/filtered_table.qza --i-phylogeny $RUN_Qiime2/rooted_tree.qza --p-max-depth 4000 --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/alpha_rarefaction.qzv&
wait
echo "MMEDS_STAGE_4"
qiime feature-classifier classify-sklearn --i-classifier /sc/arion/projects/MMEDS/mmeds_server_data/gg-13-8-99-nb-classifier.qza --i-reads $RUN_Qiime2/rep_seqs_dada2.qza --o-classification $RUN_Qiime2/taxonomy.qza --p-n-jobs 10
qiime taxa barplot --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --o-visualization $RUN_Qiime2/taxa_bar_plot.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ExampleMetaData-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ExampleMetaData-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ExampleMetaData --o-visualization $RUN_Qiime2/ancom-ExampleMetaData.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/ExampleMetaData_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ExampleMetaData-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ExampleMetaData-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ExampleMetaData --o-visualization $RUN_Qiime2/ancom-ExampleMetaData-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-AliquotID-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-AliquotID-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column AliquotID --o-visualization $RUN_Qiime2/ancom-AliquotID.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/AliquotID_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-AliquotID-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-AliquotID-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column AliquotID --o-visualization $RUN_Qiime2/ancom-AliquotID-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenBodySite-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenBodySite-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenBodySite --o-visualization $RUN_Qiime2/ancom-SpecimenBodySite.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SpecimenBodySite_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenBodySite-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenBodySite-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenBodySite --o-visualization $RUN_Qiime2/ancom-SpecimenBodySite-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-UberonCodeBodySite-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-UberonCodeBodySite-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column UberonCodeBodySite --o-visualization $RUN_Qiime2/ancom-UberonCodeBodySite.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/UberonCodeBodySite_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-UberonCodeBodySite-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-UberonCodeBodySite-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column UberonCodeBodySite --o-visualization $RUN_Qiime2/ancom-UberonCodeBodySite-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Biome-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Biome-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Biome --o-visualization $RUN_Qiime2/ancom-Biome.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/Biome_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Biome-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Biome-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Biome --o-visualization $RUN_Qiime2/ancom-Biome-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Ethnicity-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Ethnicity-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Ethnicity --o-visualization $RUN_Qiime2/ancom-Ethnicity.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/Ethnicity_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Ethnicity-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Ethnicity-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Ethnicity --o-visualization $RUN_Qiime2/ancom-Ethnicity-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Genotype-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Genotype-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Genotype --o-visualization $RUN_Qiime2/ancom-Genotype.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/Genotype_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Genotype-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Genotype-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Genotype --o-visualization $RUN_Qiime2/ancom-Genotype-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-HeightDateCollected-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-HeightDateCollected-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column HeightDateCollected --o-visualization $RUN_Qiime2/ancom-HeightDateCollected.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/HeightDateCollected_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-HeightDateCollected-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-HeightDateCollected-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column HeightDateCollected --o-visualization $RUN_Qiime2/ancom-HeightDateCollected-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ICDCode-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ICDCode-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ICDCode --o-visualization $RUN_Qiime2/ancom-ICDCode.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/ICDCode_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ICDCode-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ICDCode-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ICDCode --o-visualization $RUN_Qiime2/ancom-ICDCode-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-IllnessEndDate-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-IllnessEndDate-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column IllnessEndDate --o-visualization $RUN_Qiime2/ancom-IllnessEndDate.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/IllnessEndDate_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-IllnessEndDate-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-IllnessEndDate-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column IllnessEndDate --o-visualization $RUN_Qiime2/ancom-IllnessEndDate-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-IllnessNotes-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-IllnessNotes-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column IllnessNotes --o-visualization $RUN_Qiime2/ancom-IllnessNotes.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/IllnessNotes_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-IllnessNotes-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-IllnessNotes-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column IllnessNotes --o-visualization $RUN_Qiime2/ancom-IllnessNotes-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-IllnessStartDate-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-IllnessStartDate-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column IllnessStartDate --o-visualization $RUN_Qiime2/ancom-IllnessStartDate.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/IllnessStartDate_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-IllnessStartDate-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-IllnessStartDate-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column IllnessStartDate --o-visualization $RUN_Qiime2/ancom-IllnessStartDate-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionEndDate-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionEndDate-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionEndDate --o-visualization $RUN_Qiime2/ancom-InterventionEndDate.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/InterventionEndDate_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionEndDate-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionEndDate-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionEndDate --o-visualization $RUN_Qiime2/ancom-InterventionEndDate-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionNotes-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionNotes-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionNotes --o-visualization $RUN_Qiime2/ancom-InterventionNotes.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/InterventionNotes_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionNotes-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionNotes-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionNotes --o-visualization $RUN_Qiime2/ancom-InterventionNotes-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionStartDate-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionStartDate-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionStartDate --o-visualization $RUN_Qiime2/ancom-InterventionStartDate.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/InterventionStartDate_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionStartDate-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionStartDate-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionStartDate --o-visualization $RUN_Qiime2/ancom-InterventionStartDate-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionCode-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionCode-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionCode --o-visualization $RUN_Qiime2/ancom-InterventionCode.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/InterventionCode_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionCode-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionCode-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionCode --o-visualization $RUN_Qiime2/ancom-InterventionCode-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionName-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionName-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionName --o-visualization $RUN_Qiime2/ancom-InterventionName.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/InterventionName_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-InterventionName-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-InterventionName-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column InterventionName --o-visualization $RUN_Qiime2/ancom-InterventionName-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-BarcodeSequence-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-BarcodeSequence-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column BarcodeSequence --o-visualization $RUN_Qiime2/ancom-BarcodeSequence.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/BarcodeSequence_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-BarcodeSequence-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-BarcodeSequence-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column BarcodeSequence --o-visualization $RUN_Qiime2/ancom-BarcodeSequence-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-RawDataID-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-RawDataID-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column RawDataID --o-visualization $RUN_Qiime2/ancom-RawDataID.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/RawDataID_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-RawDataID-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-RawDataID-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column RawDataID --o-visualization $RUN_Qiime2/ancom-RawDataID-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-RawDataNotes-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-RawDataNotes-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column RawDataNotes --o-visualization $RUN_Qiime2/ancom-RawDataNotes.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/RawDataNotes_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-RawDataNotes-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-RawDataNotes-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column RawDataNotes --o-visualization $RUN_Qiime2/ancom-RawDataNotes-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-RawDataDatePerformed-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-RawDataDatePerformed-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column RawDataDatePerformed --o-visualization $RUN_Qiime2/ancom-RawDataDatePerformed.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/RawDataDatePerformed_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-RawDataDatePerformed-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-RawDataDatePerformed-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column RawDataDatePerformed --o-visualization $RUN_Qiime2/ancom-RawDataDatePerformed-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-RawDataProtocolID-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-RawDataProtocolID-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column RawDataProtocolID --o-visualization $RUN_Qiime2/ancom-RawDataProtocolID.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/RawDataProtocolID_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-RawDataProtocolID-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-RawDataProtocolID-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column RawDataProtocolID --o-visualization $RUN_Qiime2/ancom-RawDataProtocolID-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-TargetGene-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-TargetGene-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column TargetGene --o-visualization $RUN_Qiime2/ancom-TargetGene.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/TargetGene_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-TargetGene-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-TargetGene-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column TargetGene --o-visualization $RUN_Qiime2/ancom-TargetGene-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ResultID-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ResultID-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ResultID --o-visualization $RUN_Qiime2/ancom-ResultID.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/ResultID_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ResultID-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ResultID-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ResultID --o-visualization $RUN_Qiime2/ancom-ResultID-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ResultsDatePerformed-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ResultsDatePerformed-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ResultsDatePerformed --o-visualization $RUN_Qiime2/ancom-ResultsDatePerformed.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/ResultsDatePerformed_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ResultsDatePerformed-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ResultsDatePerformed-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ResultsDatePerformed --o-visualization $RUN_Qiime2/ancom-ResultsDatePerformed-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ResultsProtocolID-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ResultsProtocolID-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ResultsProtocolID --o-visualization $RUN_Qiime2/ancom-ResultsProtocolID.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/ResultsProtocolID_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ResultsProtocolID-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ResultsProtocolID-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ResultsProtocolID --o-visualization $RUN_Qiime2/ancom-ResultsProtocolID-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ResultsMethod-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ResultsMethod-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ResultsMethod --o-visualization $RUN_Qiime2/ancom-ResultsMethod.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/ResultsMethod_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-ResultsMethod-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-ResultsMethod-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column ResultsMethod --o-visualization $RUN_Qiime2/ancom-ResultsMethod-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SampleID-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SampleID-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SampleID --o-visualization $RUN_Qiime2/ancom-SampleID.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SampleID_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SampleID-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SampleID-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SampleID --o-visualization $RUN_Qiime2/ancom-SampleID-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SampleDatePerformed-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SampleDatePerformed-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SampleDatePerformed --o-visualization $RUN_Qiime2/ancom-SampleDatePerformed.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SampleDatePerformed_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SampleDatePerformed-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SampleDatePerformed-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SampleDatePerformed --o-visualization $RUN_Qiime2/ancom-SampleDatePerformed-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SampleProtocolID-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SampleProtocolID-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SampleProtocolID --o-visualization $RUN_Qiime2/ancom-SampleProtocolID.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SampleProtocolID_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SampleProtocolID-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SampleProtocolID-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SampleProtocolID --o-visualization $RUN_Qiime2/ancom-SampleProtocolID-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SampleToolVersion-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SampleToolVersion-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SampleToolVersion --o-visualization $RUN_Qiime2/ancom-SampleToolVersion.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SampleToolVersion_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SampleToolVersion-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SampleToolVersion-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SampleToolVersion --o-visualization $RUN_Qiime2/ancom-SampleToolVersion-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenCollectionDate-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenCollectionDate-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenCollectionDate --o-visualization $RUN_Qiime2/ancom-SpecimenCollectionDate.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SpecimenCollectionDate_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenCollectionDate-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenCollectionDate-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenCollectionDate --o-visualization $RUN_Qiime2/ancom-SpecimenCollectionDate-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenCollectionTime-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenCollectionTime-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenCollectionTime --o-visualization $RUN_Qiime2/ancom-SpecimenCollectionTime.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SpecimenCollectionTime_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenCollectionTime-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenCollectionTime-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenCollectionTime --o-visualization $RUN_Qiime2/ancom-SpecimenCollectionTime-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenID-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenID-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenID --o-visualization $RUN_Qiime2/ancom-SpecimenID.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SpecimenID_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenID-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenID-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenID --o-visualization $RUN_Qiime2/ancom-SpecimenID-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-StorageFreezer-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-StorageFreezer-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column StorageFreezer --o-visualization $RUN_Qiime2/ancom-StorageFreezer.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/StorageFreezer_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-StorageFreezer-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-StorageFreezer-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column StorageFreezer --o-visualization $RUN_Qiime2/ancom-StorageFreezer-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Nationality-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Nationality-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Nationality --o-visualization $RUN_Qiime2/ancom-Nationality.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/Nationality_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Nationality-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Nationality-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Nationality --o-visualization $RUN_Qiime2/ancom-Nationality-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Sex-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Sex-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Sex --o-visualization $RUN_Qiime2/ancom-Sex.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/Sex_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-Sex-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-Sex-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column Sex --o-visualization $RUN_Qiime2/ancom-Sex-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenType-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenType-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenType --o-visualization $RUN_Qiime2/ancom-SpecimenType.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/SpecimenType_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-SpecimenType-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-SpecimenType-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column SpecimenType --o-visualization $RUN_Qiime2/ancom-SpecimenType-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-UberonCodeType-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-UberonCodeType-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column UberonCodeType --o-visualization $RUN_Qiime2/ancom-UberonCodeType.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/UberonCodeType_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-UberonCodeType-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-UberonCodeType-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column UberonCodeType --o-visualization $RUN_Qiime2/ancom-UberonCodeType-l2.qzv
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-WeightDateCollected-table.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-WeightDateCollected-table.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column WeightDateCollected --o-visualization $RUN_Qiime2/ancom-WeightDateCollected.qzv
qiime taxa collapse --i-table $RUN_Qiime2/filtered_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --p-level 2 --o-collapsed-table $RUN_Qiime2/WeightDateCollected_table_l2.qza
qiime composition add-pseudocount --i-table $RUN_Qiime2/filtered_table.qza --o-composition-table $RUN_Qiime2/comp-WeightDateCollected-table-l2.qza
qiime composition ancom --i-table $RUN_Qiime2/comp-WeightDateCollected-table-l2.qza --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --p-transform-function log --m-metadata-column WeightDateCollected --o-visualization $RUN_Qiime2/ancom-WeightDateCollected-l2.qzv
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ExampleMetaData --o-grouped-metadata-file $RUN_Qiime2/grouped_ExampleMetaData_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column AliquotID --o-grouped-metadata-file $RUN_Qiime2/grouped_AliquotID_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenBodySite --o-grouped-metadata-file $RUN_Qiime2/grouped_SpecimenBodySite_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column UberonCodeBodySite --o-grouped-metadata-file $RUN_Qiime2/grouped_UberonCodeBodySite_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Biome --o-grouped-metadata-file $RUN_Qiime2/grouped_Biome_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Ethnicity --o-grouped-metadata-file $RUN_Qiime2/grouped_Ethnicity_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Genotype --o-grouped-metadata-file $RUN_Qiime2/grouped_Genotype_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column HeightDateCollected --o-grouped-metadata-file $RUN_Qiime2/grouped_HeightDateCollected_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ICDCode --o-grouped-metadata-file $RUN_Qiime2/grouped_ICDCode_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessEndDate --o-grouped-metadata-file $RUN_Qiime2/grouped_IllnessEndDate_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessNotes --o-grouped-metadata-file $RUN_Qiime2/grouped_IllnessNotes_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessStartDate --o-grouped-metadata-file $RUN_Qiime2/grouped_IllnessStartDate_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionEndDate --o-grouped-metadata-file $RUN_Qiime2/grouped_InterventionEndDate_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionNotes --o-grouped-metadata-file $RUN_Qiime2/grouped_InterventionNotes_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionStartDate --o-grouped-metadata-file $RUN_Qiime2/grouped_InterventionStartDate_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionCode --o-grouped-metadata-file $RUN_Qiime2/grouped_InterventionCode_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionName --o-grouped-metadata-file $RUN_Qiime2/grouped_InterventionName_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column BarcodeSequence --o-grouped-metadata-file $RUN_Qiime2/grouped_BarcodeSequence_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataID --o-grouped-metadata-file $RUN_Qiime2/grouped_RawDataID_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataNotes --o-grouped-metadata-file $RUN_Qiime2/grouped_RawDataNotes_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataDatePerformed --o-grouped-metadata-file $RUN_Qiime2/grouped_RawDataDatePerformed_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataProtocolID --o-grouped-metadata-file $RUN_Qiime2/grouped_RawDataProtocolID_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column TargetGene --o-grouped-metadata-file $RUN_Qiime2/grouped_TargetGene_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultID --o-grouped-metadata-file $RUN_Qiime2/grouped_ResultID_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsDatePerformed --o-grouped-metadata-file $RUN_Qiime2/grouped_ResultsDatePerformed_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsProtocolID --o-grouped-metadata-file $RUN_Qiime2/grouped_ResultsProtocolID_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsMethod --o-grouped-metadata-file $RUN_Qiime2/grouped_ResultsMethod_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleID --o-grouped-metadata-file $RUN_Qiime2/grouped_SampleID_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleDatePerformed --o-grouped-metadata-file $RUN_Qiime2/grouped_SampleDatePerformed_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleProtocolID --o-grouped-metadata-file $RUN_Qiime2/grouped_SampleProtocolID_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleToolVersion --o-grouped-metadata-file $RUN_Qiime2/grouped_SampleToolVersion_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenCollectionDate --o-grouped-metadata-file $RUN_Qiime2/grouped_SpecimenCollectionDate_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenCollectionTime --o-grouped-metadata-file $RUN_Qiime2/grouped_SpecimenCollectionTime_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenID --o-grouped-metadata-file $RUN_Qiime2/grouped_SpecimenID_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column StorageFreezer --o-grouped-metadata-file $RUN_Qiime2/grouped_StorageFreezer_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Nationality --o-grouped-metadata-file $RUN_Qiime2/grouped_Nationality_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Sex --o-grouped-metadata-file $RUN_Qiime2/grouped_Sex_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenType --o-grouped-metadata-file $RUN_Qiime2/grouped_SpecimenType_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column UberonCodeType --o-grouped-metadata-file $RUN_Qiime2/grouped_UberonCodeType_mapping_file.tsv;
make_grouped_mapping_file.py --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column WeightDateCollected --o-grouped-metadata-file $RUN_Qiime2/grouped_WeightDateCollected_mapping_file.tsv;
# source activate qiime2-2020.8.0;
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ExampleMetaData --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_ExampleMetaData_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_ExampleMetaData_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_ExampleMetaData_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_ExampleMetaData_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column AliquotID --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_AliquotID_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_AliquotID_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_AliquotID_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_AliquotID_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenBodySite --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SpecimenBodySite_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SpecimenBodySite_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SpecimenBodySite_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SpecimenBodySite_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column UberonCodeBodySite --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_UberonCodeBodySite_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_UberonCodeBodySite_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_UberonCodeBodySite_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_UberonCodeBodySite_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Biome --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_Biome_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_Biome_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_Biome_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_Biome_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Ethnicity --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_Ethnicity_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_Ethnicity_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_Ethnicity_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_Ethnicity_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Genotype --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_Genotype_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_Genotype_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_Genotype_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_Genotype_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column HeightDateCollected --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_HeightDateCollected_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_HeightDateCollected_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_HeightDateCollected_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_HeightDateCollected_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ICDCode --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_ICDCode_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_ICDCode_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_ICDCode_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_ICDCode_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessEndDate --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_IllnessEndDate_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_IllnessEndDate_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_IllnessEndDate_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_IllnessEndDate_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessNotes --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_IllnessNotes_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_IllnessNotes_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_IllnessNotes_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_IllnessNotes_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column IllnessStartDate --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_IllnessStartDate_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_IllnessStartDate_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_IllnessStartDate_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_IllnessStartDate_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionEndDate --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_InterventionEndDate_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_InterventionEndDate_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_InterventionEndDate_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_InterventionEndDate_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionNotes --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_InterventionNotes_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_InterventionNotes_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_InterventionNotes_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_InterventionNotes_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionStartDate --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_InterventionStartDate_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_InterventionStartDate_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_InterventionStartDate_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_InterventionStartDate_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionCode --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_InterventionCode_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_InterventionCode_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_InterventionCode_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_InterventionCode_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column InterventionName --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_InterventionName_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_InterventionName_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_InterventionName_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_InterventionName_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column BarcodeSequence --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_BarcodeSequence_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_BarcodeSequence_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_BarcodeSequence_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_BarcodeSequence_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataID --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_RawDataID_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_RawDataID_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_RawDataID_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_RawDataID_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataNotes --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_RawDataNotes_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_RawDataNotes_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_RawDataNotes_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_RawDataNotes_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataDatePerformed --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_RawDataDatePerformed_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_RawDataDatePerformed_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_RawDataDatePerformed_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_RawDataDatePerformed_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column RawDataProtocolID --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_RawDataProtocolID_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_RawDataProtocolID_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_RawDataProtocolID_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_RawDataProtocolID_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column TargetGene --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_TargetGene_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_TargetGene_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_TargetGene_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_TargetGene_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultID --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_ResultID_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_ResultID_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_ResultID_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_ResultID_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsDatePerformed --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_ResultsDatePerformed_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_ResultsDatePerformed_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_ResultsDatePerformed_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_ResultsDatePerformed_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsProtocolID --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_ResultsProtocolID_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_ResultsProtocolID_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_ResultsProtocolID_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_ResultsProtocolID_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column ResultsMethod --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_ResultsMethod_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_ResultsMethod_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_ResultsMethod_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_ResultsMethod_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleID --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SampleID_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SampleID_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SampleID_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SampleID_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleDatePerformed --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SampleDatePerformed_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SampleDatePerformed_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SampleDatePerformed_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SampleDatePerformed_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleProtocolID --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SampleProtocolID_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SampleProtocolID_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SampleProtocolID_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SampleProtocolID_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SampleToolVersion --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SampleToolVersion_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SampleToolVersion_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SampleToolVersion_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SampleToolVersion_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenCollectionDate --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SpecimenCollectionDate_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SpecimenCollectionDate_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SpecimenCollectionDate_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SpecimenCollectionDate_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenCollectionTime --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SpecimenCollectionTime_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SpecimenCollectionTime_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SpecimenCollectionTime_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SpecimenCollectionTime_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenID --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SpecimenID_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SpecimenID_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SpecimenID_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SpecimenID_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column StorageFreezer --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_StorageFreezer_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_StorageFreezer_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_StorageFreezer_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_StorageFreezer_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Nationality --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_Nationality_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_Nationality_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_Nationality_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_Nationality_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column Sex --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_Sex_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_Sex_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_Sex_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_Sex_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column SpecimenType --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_SpecimenType_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_SpecimenType_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_SpecimenType_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_SpecimenType_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column UberonCodeType --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_UberonCodeType_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_UberonCodeType_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_UberonCodeType_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_UberonCodeType_taxa_bar_plot.qzv
qiime feature-table group --i-table $RUN_Qiime2/filtered_table.qza --p-axis 'sample' --m-metadata-file $RUN_Qiime2/qiime_mapping_file.tsv --m-metadata-column WeightDateCollected --p-mode 'mean-ceiling' --o-grouped-table $RUN_Qiime2/grouped_WeightDateCollected_table.qza;
qiime taxa barplot --i-table $RUN_Qiime2/grouped_WeightDateCollected_table.qza --i-taxonomy $RUN_Qiime2/taxonomy.qza --m-metadata-file $RUN_Qiime2/grouped_WeightDateCollected_mapping_file.tsv --o-visualization $RUN_Qiime2/grouped_WeightDateCollected_taxa_bar_plot.qzv
