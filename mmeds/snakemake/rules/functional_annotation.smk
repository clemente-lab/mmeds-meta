rule picrust2_core:
    """ Generate picrust2 tables for input feature table """
    input:
        rep_seqs = "tables/rep_seqs_table.fasta",
        biom_feature_table = "tables/asv_table.biom"
    output:
        directory("picrust2_out")
    conda:
        "picrust2"
    shell:
        "picrust2_pipeline.py "
        "-s {input.rep_seqs} "
        "-i {input.biom_feature_table} "
        "-o {output} "
        "--stratified"
