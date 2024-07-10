configfile: "config_file.yaml"
report: "report.rst"

include: "{snakemake_dir}/differential_abundance.smk"
include: "{snakemake_dir}/file_manipulation.smk"
include: "{snakemake_dir}/table_filtering.smk"

import pandas as pd
metadata = pd.read_csv("tables/qiime_mapping_file.tsv", sep='\t', header=[0], skiprows=[1])

comparisons = {}
for class in config["class"]:
    categories = metadata[class].unique()
    
    if len(categories) < 3:
        comparisons[class] = expand("{table}", table=config['tables'])
        continue

    comparisons[class] = []
    for i in range(len(categories)-1):
        for j in range(i+1, len(categories)):
            comparisons[class].append(expand("{table}_{category}_{class1}_or_{class2}", 
                                             table=config['tables'], category=[class], class1=categories[i], class2=categories[j]))



rule results:
    input:
        "results/lefse_results.taxa_table_L6.Group.Group.tsv"
