import pandas as pd
from copy import deepcopy
from pathlib import Path
from mmeds.config import TOOLS_DIR
from subprocess import run

"""
This common.smk file, following snakemake conventions, contains all the python logic necessary for generating the snakemake rule DAG
"""

metadata = pd.read_csv("tables/qiime_mapping_file.tsv", sep='\t', header=[0], skiprows=[1], dtype='str')

def pairwise_splits(wildcards, tool, vars):
    if "tables" in config:
        tables = config["tables"]
    else:
        tables = [f"taxa_table_L{x}" for x in config["taxa_levels"]]

    subclasses = False
    if tool == "lefse" and "subclasses" in config and config["subclasses"]:
        subclasses = deepcopy(config["subclasses"])

    splits = []
    for table in tables:
        if not Path(f"tables/{table}.tsv").exists():
            extract_feature_table_subprocess(table)
        table_df = pd.read_csv(f"tables/{table}.tsv", sep='\t', header=[0], index_col=0)
        filtered_metadata = metadata.loc[metadata["#SampleID"].isin(table_df.columns)]
        for var in vars:
            categories = list(filtered_metadata[var].unique())
            categories = [c for c in categories if str(c) != "nan"]
            value_counts = filtered_metadata[var].value_counts()

            if len(categories) < 2:
                # Only one value in the class, nothing to compare
                continue

            if len(categories) < 3:
                # Exactly two values in the class, no pairwise checks needed
                if not sufficient_values(value_counts, categories[0], categories[1]):
                    continue
                if tool == "lefse":
                    splits += expand("results/{var}/lefse_plot.{feature_table}.{var}.NA.pdf",
                                     feature_table=table, var=var)
                    if subclasses:
                        splits += expand("results/{var}/lefse_plot.{feature_table}.{var}.{subclass}.pdf",
                                        feature_table=table, var=var, subclass=subclasses)
                elif tool == "ancombc":
                    splits += expand("differential_abundance/{var}/ancom-bc_barplot.{feature_table}.{var}::{cat}.qzv",
                                    feature_table=table, var=var, cat=categories[0])
                continue

            for i in range(len(categories)-1):
                if tool == "ancombc":
                    splits += expand("differential_abundance/{var}/ancom-bc_barplot.{feature_table}.{var}::{cat}.qzv",
                                     feature_table=table, var=var, cat=categories[i])
                else:
                    splits += expand("results/{var}/lefse_plot_strict.{feature_table}.{var}.NA.pdf",
                                         feature_table=table, var=var)
                    if subclasses:
                        splits += expand("results/{var}/lefse_plot_strict.{feature_table}.{var}.{subclass}.pdf",
                                             feature_table=table, var=var, subclass=subclasses)
                for j in range(i+1, len(categories)):
                    # Perform pairwise checks
                    if not sufficient_values(value_counts, categories[i], categories[j]):
                        continue
                    if tool == "lefse":
                        splits += expand("results/{var}/lefse_plot.{feature_table}.{var}-{cat1}-or-{cat2}.{var}.NA.pdf",
                                         feature_table=table, var=var, cat1=categories[i], cat2=categories[j])
                        if subclasses:
                            splits += expand("results/{var}/lefse_plot.{feature_table}.{var}-{cat1}-or-{cat2}.{var}.{subclass}.pdf",
                                             feature_table=table, var=var, cat1=categories[i], cat2=categories[j], subclass=subclasses)
    return splits

def ancombc_splits(wildcards):
    return pairwise_splits(wildcards, "ancombc", config["metadata"])

def lefse_splits(wildcards):
    """ 
    Replace occurrences where class==subclass with subclass="NA", which is the default behavior, this handles the issue at the DAG level
        e.g. separated: ["results/class/lefse_plot", "feature_table_class_cat1_or_cat2", "class", "subclass", "pdf"]
    """
    splits = pairwise_splits(wildcards, "lefse", config["classes"])
    formatted_splits = []
    for s in splits:
        separated = s.split(".")
        if separated[-2] == separated[-3]:
            separated[-2] = "NA"
        formatted_splits += [".".join(separated)]

    return formatted_splits

def lefse_get_subclass(wildcards):
    subclass = wildcards["class"] if wildcards["subclass"] == "NA" else wildcards["subclass"]
    return subclass

def sufficient_values(value_counts, cat1, cat2, threshold=2):
    """ Check if two categories have enough samples for a comparison """
    if value_counts[cat1] < threshold or value_counts[cat2] < threshold:
        return False
    return True

def demux_single_option(wildcards):
    """ Studies from MSQ past their 90th run require no golay error correction, all others require rev comp mapping barcodes """
    components = wildcards.sequencing_run.split("_")
    if "MSQ" in components and int(components[-1]) > 90:
        return "--p-no-golay-error-correction"
    return "--p-rev-comp-mapping-barcodes"

def get_lefse_plot_options():
    opts = ""
    if "clean_strings" in config and config["clean_strings"] is not None and not config["clean_strings"]:
        opts += "--no-string-clean "
    if "plot_max_rows" in config and type(config["plot_max_rows"]) is int and config["plot_max_rows"] > 0:
        opts += f"--row-max {config['plot_max_rows']} "
    if "match_string" in config and config["match_string"]:
        opts += f"--match-string {config['match_string']} "
    return opts

def get_tool_dir():
    return TOOLS_DIR

def extract_feature_table_subprocess(table):
    qza_file = Path(f"tables/{table}.qza")
    tsv_file = Path(f"tables/{table}.tsv")
    tmp_dir = Path("tables/tmp_unzip")

    if not qza_file.exists():
        raise FileNotFoundError(f"{qza_file.name} not found in tables folder")

    run(["unzip", "-qq", "-jo", str(qza_file), "-d", str(tmp_dir)])
    run(["biom", "convert", "--to-tsv", "-i", str(tmp_dir / "feature-table.biom"), "-o", str(tsv_file)])
    run(["rm", "-rf", str(tmp_dir)])
    run(["sed", "-i", "1d;2s/^#//", str(tsv_file)])

