configfile: "config_file.yaml"
report: "report.rst"

include: "{snakemake_dir}/differential_abundance.smk"
include: "{snakemake_dir}/file_manipulation.smk"
include: "{snakemake_dir}/table_filtering.smk"
include: "{snakemake_dir}/common.smk"

rule results:
    input:
        lefse_splits
