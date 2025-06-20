# TODO: programmatically make classifiers one rule
rule classify_taxonomy_greengenes:
    """ Classify sequences with GreenGenes """
    threads: 10
    input:
        classifier = "tables/gg-13-8-99-nb-2020-8-0.qza",
        rep_seqs = "tables/rep_seqs_table.qza"
    output:
        "tables/taxonomy.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime feature-classifier classify-sklearn "
        "--i-classifier {input.classifier} "
        "--i-reads {input.rep_seqs} "
        "--p-n-jobs {threads} "
        "--o-classification {output}"

rule classify_taxonomy_greengenes2:
    """ Classify sequences with GreenGenes2 """
    threads: 10
    input:
        classifier = "tables/greengenes2.2020-10.nb-classifier.qza",
        rep_seqs = "tables/rep_seqs_table.qza"
    output:
        "tables/taxonomy.qza"
    conda:
        "qiime2-2023.9"
    shell:
        "qiime feature-classifier classify-sklearn "
        "--i-classifier {input.classifier} "
        "--i-reads {input.rep_seqs} "
        "--p-n-jobs {threads} "
        "--o-classification {output}"

rule classify_taxonomy_greengenes2_old_qiime2:
    threads: 10
    input:
        classifier = "tables/greengenes2.2020-10.nb-classifier.old_qiime2.qza",
        rep_seqs = "tables/rep_seqs_table.qza"
    output:
        "tables/taxonomy.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime feature-classifier classify-sklearn "
        "--i-classifier {input.classifier} "
        "--i-reads {input.rep_seqs} "
        "--p-n-jobs {threads} "
        "--o-classification {output}"

rule classify_taxonomy_silva:
    """ Classify sequences with SILVA """
    threads: 10
    input:
        classifier = "tables/silva-138-99-nb-classifier.qza",
        rep_seqs = "tables/rep_seqs_table.qza"
    output:
        "tables/taxonomy.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime feature-classifier classify-sklearn "
        "--i-classifier {input.classifier} "
        "--i-reads {input.rep_seqs} "
        "--p-n-jobs {threads} "
        "--o-classification {output}"

rule classify_taxonomy_test:
    """ Dummy classification for automated testing """
    threads: 10
    input:
        classifier = "tables/dummy_classifier.qza",
        rep_seqs = "tables/rep_seqs_table.qza"
    output:
        "tables/taxonomy.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime feature-classifier classify-sklearn "
        "--i-classifier {input.classifier} "
        "--i-reads {input.rep_seqs} "
        "--p-n-jobs {threads} "
        "--o-classification {output}"

rule taxonomy_collapse:
    """ Collapse table to a particular taxonomic level using q2-taxa """
    input:
        feature_table = "tables/asv_table.qza",
        taxonomy = "tables/taxonomy.qza"
    output:
        "tables/taxa_table_L{level,[1-8]}.qza"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime taxa collapse "
        "--i-table {input.feature_table} "
        "--i-taxonomy {input.taxonomy} "
        "--p-level {wildcards.level} "
        "--o-collapsed-table {output}"

rule taxonomic_barplot:
    """ Generate standard taxa barplot qzv using q2-taxa """
    input:
        feature_table = "tables/asv_table.qza",
        taxonomy = "tables/taxonomy.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "tables/taxa_barplot.qzv"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime taxa barplot "
        "--i-table {input.feature_table} "
        "--i-taxonomy {input.taxonomy} "
        "--m-metadata-file {input.mapping_file} "
        "--o-visualization {output}"

