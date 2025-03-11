rule differential_abundance_ancom_bc:
    input:
        feature_table = "tables/{table}.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        diffs = "differential_abundance/{var}/ancom-bc_diffs.{table}.{var}::{cat}.qza",
        barplot = "differential_abundance/{var}/ancom-bc_barplot.{table}.{var}::{cat}.qzv"
    conda:
        "qiime2-2023.9"
    shell:
        """
        qiime composition ancombc --verbose --i-table {input.feature_table} --m-metadata-file {input.mapping_file} --p-formula {wildcards.var} --p-reference-levels {wildcards.var}::{wildcards.cat} --o-differentials {output.diffs}
        qiime composition da-barplot --verbose --i-data {output.diffs} --p-significance-threshold 0.05 --p-label-limit 2000 --o-visualization {output.barplot}
        """

rule differential_abundance_lefse:
    input:
        "tables/{class}/lefse_format.{table}.{class}.{subclass}.tsv"
    output:
        lefse_input = "tables/{class}/lefse_input.{table}.{class}.{subclass}.lefse",
        lefse_results = "results/{class}/lefse_results.{table}.{class}.{subclass}.tsv"
    conda:
        "lefse"
    shell:
        """
        lefse_format_input.py {input} {output.lefse_input} -c 1 -s 2 -u 3 -o 1000000
        lefse_run.py {output.lefse_input} {output.lefse_results}
        sed -i "1s/^/RawTaxa\tX\tGroup\tLDA\tpval\\n/" {output.lefse_results}
        """

rule differential_abundance_lefse_strict:
    input:
        "tables/{class}/lefse_format.{table}.{class}.{subclass}.tsv"
    output:
        lefse_input = "tables/{class}/lefse_input_strict.{table}.{class}.{subclass}.lefse",
        lefse_results = "results/{class}/lefse_results_strict.{table}.{class}.{subclass}.tsv"
    conda:
        "lefse"
    shell:
        """
        lefse_format_input.py {input} {output.lefse_input} -c 1 -s 2 -u 3 -o 1000000
        lefse_run.py {output.lefse_input} {output.lefse_results} -y 1
        sed -i "1s/^/RawTaxa\tX\tGroup\tLDA\tpval\\n/" {output.lefse_results}
        """

rule plot_lefse_results:
    input:
        "results/{class}/lefse_results.{table}.{class}.{subclass}.tsv"
    output:
        "results/{class}/lefse_plot.{table}.{class}.{subclass}.pdf"
    params:
        tool_dir = get_tool_dir()
    shell:
        """
        ml R/4.1.0
        Rscript {params.tool_dir}/plot_lefse.R {input} {output}
        """

rule plot_lefse_results_strict:
    input:
        "results/{class}/lefse_results_strict.{table}.{class}.{subclass}.tsv"
    output:
        "results/{class}/lefse_plot_strict.{table}.{class}.{subclass}.pdf"
    params:
        tool_dir = get_tool_dir()
    shell:
        """
        ml R/4.1.0
        Rscript {params.tool_dir}/plot_lefse.R {input} {output} --strict
        """
        
