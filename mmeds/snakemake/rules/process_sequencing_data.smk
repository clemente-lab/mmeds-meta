rule merge_sequencing_runs:
    """ Merge the results of all sequencing runs included in a study into a single table for downstream analysis """
    input:
        feature_tables = expand("section_{sequencing_run}/table_dada2.qza", sequencing_run=config['sequencing_runs']),
        rep_seqs = expand("section_{sequencing_run}/rep_seqs_dada2.qza", sequencing_run=config['sequencing_runs'])
    output:
        feature_table = "tables/asv_table_no_reads_threshold.qza",
        rep_seqs_table = "tables/rep_seqs_table.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        """
        qiime feature-table merge --i-tables {input.feature_tables} --o-merged-table {output.feature_table}
        qiime feature-table merge-seqs --i-data {input.rep_seqs} --o-merged-data {output.rep_seqs_table}
        """

rule import_single_barcodes:
    """ Import paired-end single-barcoded multiplexed fastq data from MMEDS sequencing_runs into QIIME2 format """
    input:
        import_dir = "section_{sequencing_run}/import_dir",
        forward_reads = "section_{sequencing_run}/import_dir/forward.fastq.gz",
        reverse_reads = "section_{sequencing_run}/import_dir/reverse.fastq.gz",
        barcodes = "section_{sequencing_run}/import_dir/barcodes.fastq.gz"
    output:
        "section_{sequencing_run}/qiime_import_artifact.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime tools import "
        "--type EMPPairedEndSequences "
        "--input-path {input.import_dir} "
        "--output-path {output}"

rule import_pheniqs_sample_data:
    """ Import paired-end pheniqs-demultiplexed fastq data into QIIME2 format """
    input:
        dir = "section_{sequencing_run}/stripped_output",
    output:
        "section_{sequencing_run}/demux_file.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime tools import "
        "--type SampleData[PairedEndSequencesWithQuality] "
        "--input-format CasavaOneEightSingleLanePerSampleDirFmt "
        "--input-path {input.dir} "
        "--output-path {output}"

rule make_pheniqs_config:
    """ Create YAML file describing all barcodes and samples to Pheniqs """
    input:
        dir = "section_{sequencing_run}",
        forward_reads = "section_{sequencing_run}/import_dir/forward.fastq.gz",
        reverse_reads = "section_{sequencing_run}/import_dir/reverse.fastq.gz",
        for_barcodes = "section_{sequencing_run}/import_dir/for_barcodes.fastq.gz",
        rev_barcodes = "section_{sequencing_run}/import_dir/rev_barcodes.fastq.gz",
        mapping_file = "section_{sequencing_run}/qiime_mapping_file_{sequencing_run}.tsv"
    output:
        "section_{sequencing_run}/pheniqs_config.json",
    conda:
        "mmeds"
    shell:
        "make_pheniqs_config.py "
        "--reads-forward {input.forward_reads} "
        "--reads-reverse {input.reverse_reads} "
        "--barcodes-forward {input.for_barcodes} "
        "--barcodes-reverse {input.rev_barcodes} "
        "--mapping-file {input.mapping_file} "
        "--o-directory {input.dir}/pheniqs_output "
        "--o-config {output}"

rule build_phylogenetic_tree:
    """ Perform all QIIME2 steps necessary for building and rooting the phylogenetic tree from DADA2 sequence data """
    input:
        feature_table = "tables/asv_table.qza",
        rep_seqs = "tables/rep_seqs_table.qza"
    output:
        feature_table_viz = "tables/asv_table_viz.qzv",
        rooted_tree = "tables/rooted_tree.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        """
        qiime feature-table summarize --i-table {input.feature_table} --o-visualization {output.feature_table_viz}
        qiime alignment mafft --i-sequences {input.rep_seqs} --o-alignment temp_files/alignment.qza
        qiime alignment mask --i-alignment temp_files/alignment.qza --o-masked-alignment temp_files/masked_alignment.qza
        qiime phylogeny fasttree --i-alignment temp_files/masked_alignment.qza --o-tree temp_files/unrooted_tree.qza
        qiime phylogeny midpoint-root --i-tree temp_files/unrooted_tree.qza --o-rooted-tree tables/rooted_tree.qza
        """
