import pandas as pd
from copy import deepcopy
from pathlib import Path
from mmeds.config import TOOLS_DIR

metadata = pd.read_csv("tables/qiime_mapping_file.tsv", sep='\t', header=[0], skiprows=[1])

def lefse_splits(wildcards):
    splits = []
    for lefse_class in config["classes"]:
        categories = list(metadata[lefse_class].unique())
        categories = [c for c in categories if str(c) != "nan"]

        subclasses = []
        if "subclasses" in config and config["subclasses"]:
            subclasses = deepcopy(config["subclasses"])

        if lefse_class not in subclasses:
            subclasses += [lefse_class]

        if len(categories) < 3:
            splits += expand("results/lefse_plot.{feature_table}.{lefse_class}.{subclass}.pdf",
                             feature_table=config["tables"], lefse_class=lefse_class, subclass=subclasses)
            continue


        splits += expand("results/lefse_plot_strict.{feature_table}.{lefse_class}.{subclass}.pdf",
                         feature_table=config["tables"], lefse_class=lefse_class, subclass=subclasses)
        for i in range(len(categories)-1):
            for j in range(i+1, len(categories)):
                    splits += expand("results/lefse_plot.{feature_table}_{lefse_class}_{cat1}_or_{cat2}.{lefse_class}.{subclass}.pdf",
                                     feature_table=config["tables"], lefse_class=lefse_class, cat1=categories[i], cat2=categories[j], subclass=subclasses)
    return splits

def demux_single_option(wildcards):
    components = wildcards.sequencing_run.split("_")
    if "MSQ" in components and int(components[-1]) > 90:
        return "--p-no-golay-error-correction"
    return "--p-rev-comp-mapping-barcodes"

def get_tool_dir():
    return TOOLS_DIR
