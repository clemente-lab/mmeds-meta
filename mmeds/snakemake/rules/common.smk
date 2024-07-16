import pandas as pd
from copy import deepcopy
from pathlib import Path

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


def get_tool_dir():
    # FIXME: get TOOL_DIR from mmeds.config when snakemake is added to mmeds env
    return "~/mmeds-meta/mmeds/tools"
