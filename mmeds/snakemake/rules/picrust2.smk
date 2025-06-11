rule picrust2_core:
    """ Generate picrust2 tables for input feature table """
    input:
        rep_seqs = "tables/rep_seqs_table.fasta",
        biom_feature_table = "tables/asv_table.biom"
    output:
        picrust2_results = "picrust2_out"
    conda:
        # "qiime2-2020.8.0" # or should I use "qiime2-2023.9"
        /sc/arion/projects/MMEDS/.modules/picrust2
    shell:
        picrust2_pipeline.py -s {input.rep_seqs} -s {input.biom_feature_table} {output.picrust2_results}