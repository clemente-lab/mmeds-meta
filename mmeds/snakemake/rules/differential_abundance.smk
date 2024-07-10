rule differential_abundance_ancom_bc:
    input:
        feature_table = "tables/{table}.qza",
        mapping_file = "tables/qiime_mapping_file.tsv"
    output:
        diffs = "differential_abundance/ancom-bc_{table}_{var}_diffs.qza",
        barplot = "differential_abundance/ancom-bc_{table}_{var}_barplot.qzv"
    conda:
        "qiime2-2023.9"
    shell:
        """
        qiime composition ancombc --i-table {input.feature_table} --m-metadata-file {input.mapping_file} --p-formula {wildcards.var} --o-differentials {output.diffs}
        qiime composition da-barplot --i-data {output.diffs} --p-significance-threshold 0.05 --p-label-limit 2000 --o-visualization {output.barplot}
        """

rule differential_abundance_lefse:
    input:
        "tables/lefse_format.{table}.{class}.{subclass}.tsv"
    output:
        lefse_input = "tables/lefse_input.{table}.{class}.{subclass}.lefse",
        lefse_results = "results/lefse_results.{table}.{class}.{subclass}.tsv"
    conda:
        "/sc/arion/projects/MMEDS/.modules/lefse"
    shell:
        """
        lefse_format_input.py {input} {output.lefse_input} -c 1 -s 2 -u 3 -o 1000000
        lefse_run.py {output.lefse_input} {output.lefse_results}
        """

rule differential_abundance_lefse_strict:
    input:
        "tables/lefse_format_strict.{table}.{class}.{subclass}.tsv"
    output:
        lefse_input = "tables/lefse_input_strict.{table}.{class}.{subclass}.lefse",
        lefse_results = "results/lefse_results_strict.{table}.{class}.{subclass}.tsv"
    conda:
        "/sc/arion/projects/MMEDS/.modules/lefse"
    shell:
        """
        lefse_format_input.py {input} {output.lefse_input} -c 1 -s 2 -u 3 -o 1000000
        lefse_run.py {output.lefse_input} {output.lefse_results} -y 1
        """

