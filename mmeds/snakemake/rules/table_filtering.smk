rule filter_table_by_threshold:
    input:
        feature_table = "tables/asv_table_no_reads_threshold.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "tables/asv_table.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime feature-table filter-samples "
        "--i-table {input.feature_table} "
        "--m-metadata-file {input.mapping_file} "
        "--p-min-frequency {config[sampling_depth]} "
        "--o-filtered-table {output}"

rule filter_table_to_two_classes:
    input:
        feature_table = "tables/{table}.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "tables/{table}.{category}-{class1}-or-{class2}.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime feature-table filter-samples "
        "--i-table {input.feature_table} "
        "--m-metadata-file {input.mapping_file} "
        "--p-where \"[{wildcards.category}]==\'{wildcards.class1}\' OR [{wildcards.category}]==\'{wildcards.class2}\'\" "
        "--o-filtered-table {output}"
