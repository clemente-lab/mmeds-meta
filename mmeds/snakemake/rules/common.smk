import pandas as pd
from copy import deepcopy
from pathlib import Path
from mmeds.config import TOOLS_DIR

"""
This common.smk file, following snakemake conventions, contains all the python logic necessary for generating the snakemake rule DAG
"""

metadata = pd.read_csv("tables/qiime_mapping_file.tsv", sep='\t', header=[0], skiprows=[1])

def lefse_splits(wildcards):
    """ Calculates all the pairwise splits that should be compared by LEfSe. Will not include groups with an insufficient number of comparisons """
    splits = []
    for lefse_class in config["classes"]:
        # 'classes' in this case refer to metadata columns, whereas categories refer to the possible values of those columns
        categories = list(metadata[lefse_class].unique())

        # Discard samples with a 'nan' for the selected class. This will only work while the input has been run through MMEDS already
        categories = [c for c in categories if str(c) != "nan"]
        value_counts = metadata[lefse_class].value_counts()

        subclasses = []
        if "subclasses" in config and config["subclasses"]:
            subclasses = deepcopy(config["subclasses"])

        if len(categories) < 2:
            # Only one value in the class, nothing to compare
            continue

        if len(categories) < 3:
            # Exactly two values in the class, no pairwise checks needed
            if not sufficient_values(value_counts, categories[0], categories[1]):
                continue
            splits += expand("results/{lefse_class}/lefse_plot.{feature_table}.{lefse_class}.NA.pdf",
                             feature_table=config["tables"], lefse_class=lefse_class)
            if subclasses:
                splits += expand("results/{lefse_class}/lefse_plot.{feature_table}.{lefse_class}.{subclass}.pdf",
                                feature_table=config["tables"], lefse_class=lefse_class, subclass=subclasses)
            continue


        splits += expand("results/{lefse_class}/lefse_plot_strict.{feature_table}.{lefse_class}.{subclass}.pdf",
                         feature_table=config["tables"], lefse_class=lefse_class, subclass=subclasses)
        for i in range(len(categories)-1):
            for j in range(i+1, len(categories)):
                # Perform pairwise checks
                if not sufficient_values(value_counts, categories[i], categories[j]):
                    continue
                splits += expand("results/{lefse_class}/lefse_plot.{feature_table}_{lefse_class}_{cat1}_or_{cat2}.{lefse_class}.NA.pdf",
                                 feature_table=config["tables"], lefse_class=lefse_class, cat1=categories[i], cat2=categories[j])
                if subclasses:
                    splits += expand("results/{lefse_class}/lefse_plot.{feature_table}_{lefse_class}_{cat1}_or_{cat2}.{lefse_class}.{subclass}.pdf",
                                     feature_table=config["tables"], lefse_class=lefse_class, cat1=categories[i], cat2=categories[j], subclass=subclasses)

    formatted_splits = []
    for s in splits:
        # Replace occurrences where class==subclass with subclass="NA", which is the default behavior, this handles the issue at the DAG level
        #   e.g. separated: ["results/class/lefse_plot", "feature_table_class_cat1_or_cat2", "class", "subclass", "pdf"]
        separated = s.split(".")
        if separated[-2] == separated[-3]:
            separated[-2] = "NA"
        formatted_splits += [".".join(separated)]

    return formatted_splits

def lefse_get_subclass(wildcards):
    """ Handle class==subclass behavior at the rule level """
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

def get_tool_dir():
    return TOOLS_DIR
