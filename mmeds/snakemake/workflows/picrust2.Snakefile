configfile: "config_file.yaml"
report: "report.rst"

include: "{snakemake_dir}/common.smk"
include: "{snakemake_dir}/file_manipulation.smk"
include: "{snakemake_dir}/table_filtering.smk"

rule results:
    input:
        picrust2_core