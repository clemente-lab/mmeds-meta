configfile: "config_file.yaml"
report: "report.rst"

include: "{snakemake_dir}/demux_denoise.smk"
include: "{snakemake_dir}/process_sequencing_data.smk"
include: "{snakemake_dir}/diversity_analysis.smk"
include: "{snakemake_dir}/taxonomy.smk"
include: "{snakemake_dir}/differential_abundance.smk"

rule results:
    input:
        expand("diversity/{{metric}}_group_ANOVA.qzv", metric=config['alpha_metrics']),
        expand("diversity/{{metric}}_{{var}}_PERMANOVA.qzv", metric=config['beta_metrics'], var=config['metadata']),
        "diversity/alpha_rarefaction.qzv",
        "tables/taxa_barplot.qzv",
        expand("differential_abundance/ancom-bc_{{table}}_{{var}}_barplot.qzv", table=expand("taxa_table_L{{level}}", level=config['taxa_levels']), var=config['metadata'])
