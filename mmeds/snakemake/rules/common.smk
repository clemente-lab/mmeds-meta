import pandas as pd
from copy import deepcopy
from pathlib import Path
from mmeds.config import TOOLS_DIR

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
        table_df = pd.read_csv(f"tables/{table}.tsv", sep='\t', header=[0], index_col=0)
        filtered_metadata = metadata.loc[metadata["#SampleID"].isin(table_df.columns)]
        for var in vars:
            categories = list(filtered_metadata[var].unique())
            categories = [c for c in categories if str(c) != "nan"]
            value_counts = filtered_metadata[var].value_counts()

            if len(categories) < 2:
                continue

            if len(categories) < 3:
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
    if value_counts[cat1] < threshold or value_counts[cat2] < threshold:
        return False
    return True

def demux_single_option(wildcards):
    components = wildcards.sequencing_run.split("_")
    if "MSQ" in components and int(components[-1]) > 90:
        return "--p-no-golay-error-correction"
    return "--p-rev-comp-mapping-barcodes"

def get_tool_dir():
    return TOOLS_DIR
