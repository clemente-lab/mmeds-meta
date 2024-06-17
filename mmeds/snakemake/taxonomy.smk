rule classify_taxonomy_asvs:
    threads: 10
    input:
        classifier = "test_classifier.test",
        rep_seqs = "tables/rep_seqs_table.qza"
    output:
        "tables/taxonomy.qza"
    conda:
        "qiime-2020.8.0"
    shell:
        "qiime feature-classifier classify-sklearn "
        "--i-classifier {input.classifier} "
        "--i-reads {input.rep_seqs} "
        "--p-n-jobs {threads} "
        "--o-classification {output}"

rule taxonomy_collapse:
    input:
        feature_table = "tables/feature_table.qza",
        taxonomy = "tables/taxonomy.qza"
    output:
        "tables/taxa_table_L{level}.qza"
    conda:
        "qiime-2020.8.0"
    shell:
        "qiime taxa collapse "
        "--i-table {input.feature_table} "
        "--i-taxonomy {input.taxonomy} "
        "--p-level {wildcards.level} "
        "--o-collapsed-table {output}"

rule taxonomic_barplot:
    input:
        feature_table = "tables/feature_table.qza",
        taxonomy = "tables/taxonomy.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "tables/taxa_barplot.qzv"
    conda:
        "qiime-2020.8.0"
    shell:
        "qiime taxa barplot "
        "--i-table {input.feature_table} "
        "--i-taxonomy {input.taxonomy} "
        "--m-metadata-file {input.mapping_file} "
        "--o-visualization {output}"

