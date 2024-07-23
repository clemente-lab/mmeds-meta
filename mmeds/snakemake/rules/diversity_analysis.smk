ruleorder: diversity_core_metrics_phylogenetic > diversity_core_metrics
ruleorder: alpha_rarefaction_phylogenetic > alpha_rarefaction

rule diversity_core_metrics_phylogenetic:
    threads: 10
    input:
        feature_table = "tables/asv_table.qza",
        rooted_tree = "tables/rooted_tree.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "diversity/core_metrics_results"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime diversity core-metrics-phylogenetic "
        "--i-table {input.feature_table} "
        "--i-phylogeny {input.rooted_tree} "
        "--p-sampling-depth {config[sampling_depth]} "
        "--m-metadata-file {input.mapping_file} "
        "--p-n-jobs-or-threads {threads} "
        "--output-dir {output}"

rule diversity_core_metrics:
    threads: 10
    input:
        feature_table = "tables/asv_table.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "diversity/core_metrics_results"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime diversity core-metrics "
        "--i-table {input.feature_table} "
        "--p-sampling-depth {config[sampling_depth]} "
        "--m-metadata-file {input.mapping_file} "
        "--p-n-jobs-or-threads {threads} "
        "--output-dir {output}"

rule alpha_rarefaction_phylogenetic:
    input:
        feature_table = "tables/asv_table.qza",
        rooted_tree = "tables/rooted_tree.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "diversity/alpha_rarefaction.qzv"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime diversity alpha-rarefaction "
        "--i-table {input.feature_table} "
        "--i-phylogeny {input.rooted_tree} "
        "--m-metadata-file {input.mapping_file} "
        "--p-max-depth {config[sampling_depth]} "
        "--o-visualization {output}"

rule alpha_rarefaction:
    input:
        feature_table = "tables/asv_table.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "diversity/alpha_rarefaction.qzv"
    conda:
        "qiime2-2020.8.0"
    shell:
        "qiime diversity alpha-rarefaction "
        "--i-table {input.feature_table} "
        "--m-metadata-file {input.mapping_file} "
        "--p-max-depth {config[sampling_depth]} "
        "--o-visualization {output}"

rule alpha_diversity_ANOVA_test:
    input:
        div = "diversity/core_metrics_results",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "diversity/{metric}_group_ANOVA.qzv",
    conda:
        "qiime2-2020.8.0"
    shell:
        """
        qiime diversity alpha-group-significance --i-alpha-diversity {input.div}/{wildcards.metric}_vector.qza --m-metadata-file {input.mapping_file} --o-visualization {output}
        """

rule beta_diversity_PERMANOVA_test:
    threads: 3
    input:
        div = "diversity/core_metrics_results",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        "diversity/{metric}_{var}_PERMANOVA.qzv",
    shell:
        """
        qiime diversity beta-group-significance --i-distance-matrix {input.div}/{wildcards.metric}_distance_matrix.qza --m-metadata-file {input.mapping_file} --m-metadata-column {wildcards.var} --p-pairwise --o-visualization {output}
        """
