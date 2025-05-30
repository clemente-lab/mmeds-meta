rule demux_single_barcodes:
    """ Demultiplex a paired-end single-barcoded sequencing run with QIIME EMP"""
    input:
        seqs = "section_{sequencing_run}/qiime_import_artifact.qza",
        barcodes = "section_{sequencing_run}/qiime_mapping_file_{sequencing_run}.tsv"
    output:
        error_correction = "section_{sequencing_run}/error_correction.qza",
        demux_file = "section_{sequencing_run}/demux_file.qza"
    conda:
        "qiime2-2020.8.0"
    params:
        option = demux_single_option
    shell:
        "qiime demux emp-paired "
        "--i-seqs {input.seqs} "
        "--m-barcodes-file {input.barcodes} "
        "--m-barcodes-column BarcodeSequence "
        "{params.option} "
        "--o-error-correction-details {output.error_correction} "
        "--o-per-sample-sequences {output.demux_file}"

rule demux_dual_barcodes_pheniqs:
    """ Demultiplex a paired-end dual-barcoded sequencing run with Pheniqs """
    input:
        "section_{sequencing_run}/pheniqs_config.json"
    output:
        "section_{sequencing_run}/pheniqs_output"
    conda:
        "pheniqs"
    shell:
        "pheniqs mux --config {input}"

rule strip_error_barcodes:
    """ Filter Pheniqs output to barcodes that match exactly or differ by only one base """
    input:
        dir = "section_{sequencing_run}/pheniqs_output",
        mapping_file = "section_{sequencing_run}/qiime_mapping_file_{sequencing_run}.tsv",
    output:
        dir = "section_{sequencing_run}/stripped_output"
    conda:
        "mmeds"
    shell:
        "strip_error_barcodes.py "
        "--num-allowed-errors 1 "
        "--m-mapping-file {input.mapping_file} "
        "--i-directory {input.dir} "
        "--o-directory {output.dir}"

rule dada2_denoise:
    """ Denoise demultiplexed sequencing using QIIME and DADA2 with default params """
    threads: 10
    input:
        "section_{sequencing_run}/demux_file.qza"
    output:
        rep_seqs = "section_{sequencing_run}/rep_seqs_dada2.qza",
        feature_table = "section_{sequencing_run}/table_dada2.qza",
        stats = "section_{sequencing_run}/stats_dada2.qza",
        stats_viz = "section_{sequencing_run}/stats_dada2_viz.qzv"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime dada2 denoise-paired "
        "--i-demultiplexed-seqs {input} "
        "--p-trim-left-f 0 --p-trim-left-r 0 --p-trunc-len-f 0 --p-trunc-len-r 0 "
        "--o-representative-sequences {output.rep_seqs} "
        "--o-table {output.feature_table} "
        "--o-denoising-stats {output.stats} "
        "--p-n-threads {threads}; "
        "qiime metadata tabulate "
        "--m-input-file {output.stats} "
        "--o-visualization {output.stats_viz}"
