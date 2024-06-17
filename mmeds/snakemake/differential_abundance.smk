rule ancom_bc_run:
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
