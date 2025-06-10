rule extract_feature_table_tsv:
    """ Remove feature table biom file from qza archive, convert to readable tsv for downstream analysis """
    input:
        "tables/{table}.qza"
    output:
        "tables/{table}.tsv"
    conda:
        "mmeds_test"
    shell:
        "extract_feature_table.sh "
        "{input} "
        "{output} "
        "tables/tmp_unzip_{wildcards.table}"

rule format_metadata_qiime_to_lefse:
    """ Convert a tsv feature table to LEfSe format including class, subclass, and subject rows """
    input:
        feature_table = "tables/{table}.tsv",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "tables/{class}/lefse_format.{table}.{class}.{subclass}.tsv"
    params:
        subclass = lefse_get_subclass
    conda:
        "mmeds_test"
    shell:
        "format_lefse.py "
        "-i {input.feature_table} "
        "-m {input.mapping_file} "
        "-c {wildcards.class} "
        "-s {params.subclass} "
        "-u HostSubjectId "
        "-o {output}"
