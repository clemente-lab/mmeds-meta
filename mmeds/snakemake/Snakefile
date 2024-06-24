configfile: "test_config.yaml"
report: "report.rst"

include: "demux_denoise.smk"
include: "process_sequencing_data.smk"
include: "diversity_analysis.smk"
include: "taxonomy.smk"
include: "differential_abundance.smk"

rule results:
    input:
        expand("diversity/{metric}_group_ANOVA.qzv", metric=config['alpha_metrics']),
        expand("diversity/{metric}_{var}_PERMANOVA.qzv", metric=config['beta_metrics'], var=config['metadata']),
        "diversity/alpha_rarefaction.qzv",
        "tables/taxa_barplot.qzv",
        expand("tables/taxa_table_L{level}.qza", level=config['taxa_levels']),
        expand("differential_abundance/ancom-bc_{table}_{var}_barplot.qzv", table=expand("taxa_table_L{level}", level=config['taxa_levels']), var=config['metadata'])

