configfile: "config_file.yaml"
report: "report.rst"

include: "{snakemake_dir}/common.smk"
include: "{snakemake_dir}/file_manipulation.smk"
include: "{snakemake_dir}/table_filtering.smk"
include: "{snakemake_dir}/picrust.smk"

rule results:
    input:
        directory("picrust2_out")