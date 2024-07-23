rule extract_feature_table_tsv:
    input:
        "tables/{table}.qza"
    output:
        "tables/{table}.tsv"
    conda:
        "qiime2-2020.8.0"
    shell:
        """
        unzip -jo {input} -d tables/tmp_unzip_{wildcards.table}
        mv tables/tmp_unzip_{wildcards.table}/feature-table.biom tables/{wildcards.table}.biom
        biom convert --to-tsv -i tables/{wildcards.table}.biom -o {output}
        sed -i '1d;2s/^#//' {output}
        rm -rf tables/tmp_unzip_{wildcards.table}
        rm -f tables/{wildcards.table}.biom
        """

rule format_metadata_qiime_to_lefse:
    input:
        feature_table = "tables/{table}.tsv",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "tables/lefse_format.{table}.{class}.{subclass}.tsv"
    conda:
        "mmeds_test"
    shell:
        "format_lefse.py "
        "-i {input.feature_table} "
        "-m {input.mapping_file} "
        "-c {wildcards.class} "
        "-s {wildcards.subclass} "
        "-u HostSubjectId "
        "-o {output}"
