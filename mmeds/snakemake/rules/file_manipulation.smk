rule extract_feature_table_tsv:
    """ Remove feature table biom file from qza archive, convert to readable tsv for downstream analysis """
    input:
        "tables/{table}.qza"
    output:
        "tables/{table}.tsv"
    wildcard_constraints:
        table = "[^/]+"
    conda:
        "mmeds_test"
    shell:
        "extract_feature_table.sh "
        "{input} "
        "{output} "
        "tsv "
        "tables/tmp_unzip_{wildcards.table}"

rule extract_feature_table_biom:
    """ Remove feature table biom file from qza archive """
    input: 
        "tables/{table}.qza"
    output:
        "tables/{table}.biom"
    wildcard_constraints:
        table = "[^/]+"
    conda:
        "mmeds_test"
    shell:
        "extract_feature_table.sh "
        "{input} "
        "{output} "
        "biom "
        "tables/tmp_unzip_{wildcards.table}"

rule extract_feature_table_fasta:
    """ Remove underlying fasta data from qza archive """
    input: 
        "tables/{table}.qza"
    output:
        "tables/{table}.fasta"
    wildcard_constraints:
        table = "[^/]+"
    conda:
        "mmeds_test"
    shell:
        "extract_feature_table.sh "
        "{input} "
        "{output} "
        "fasta "
        "tables/tmp_unzip_{wildcards.table}"

rule extract_feature_table_tsv_class:
    """ Remove modified feature table biom file from qza archive, convert to readable tsv for downstream analysis """
    input:
        "tables/{class}/{table}.qza"
    output:
        "tables/{class}/{table}.tsv"
    wildcard_constraints:
        table = "[^/]+"
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

rule format_metadata_qiime_to_lefse_class:
    """ Convert a modified tsv feature table to LEfSe format including class, subclass, and subject rows """
    input:
        feature_table = "tables/{class}/{table}.tsv",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "tables/{class}/lefse_format.{table}.{class}.{subclass}.tsv"
    params:
        subclass_param = lefse_get_subclass
    conda:
        "mmeds_test"
    shell:
        "format_lefse.py "
        "-i {input.feature_table} "
        "-m {input.mapping_file} "
        "-c {wildcards.class} "
        "-s {params.subclass_param} "
        "-u HostSubjectId "
        "-o {output}"

