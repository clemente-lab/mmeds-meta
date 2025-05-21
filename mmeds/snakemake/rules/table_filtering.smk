rule filter_table_by_threshold:
    """ Filter table to a specified threshold that matches the depth at which the table will be rarefied """
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
    """ Filter a table to two specific classes in a metadata category for explicit comparison """
    input:
        feature_table = "tables/{table}.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "tables/{table}_{category}_{class1}_or_{class2}.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime feature-table filter-samples "
        "--i-table {input.feature_table} "
        "--m-metadata-file {input.mapping_file} "
        "--p-where \"[{wildcards.category}]==\'{wildcards.class1}\' OR [{wildcards.category}]==\'{wildcards.class2}\'\" "
        "--o-filtered-table {output}"
