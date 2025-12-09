library(argparser)

parser <- arg_parser("parse arguments", hide.opts=TRUE)
parser <- add_argument(parser, "results-table", nargs=1, help="Input benchdamic results table")
parser <- add_argument(parser, "metadata-column", nargs=1, help="Name of grouping, for file names")
parser <- add_argument(parser, "metadata-values", nargs=2, help="Two comma-separated values in the metadata category \
                                                                 for labelling, positive value first") 
parser <- add_argument(parser, "out-dir", nargs=1, help="Directory for outputting results")
parser <- add_argument(parser, "--string-clean-level", default=2, help="0=No string cleaning; 1=Non-strict string cleaning; 2=Strict string cleaning;")
parser <- add_argument(parser, "--label-level", default=2, help="0=Only label features that match args from --include-labels; \
                                                                 1=Label matching args and all significant above qval thresh; \
                                                                 2=Label matching args and all significant above pval thresh")
parser <- add_argument(parser, "--include-labels", nargs=Inf, help="Any number of comma-separated values to use with grep \
                                                                    to determine which features to label in resulting plots")

args <- parse_args(parser)
print(args)

library(this.path)

# MMEDS R utils
source(paste(this.dir(), "R_utils.R", sep="/"))

# Prevents Rplots.pdf being generated in working dir
pdf(NULL)

var <- args$metadata_column
valPos <- args$metadata_values[1]
valNeg <- args$metadata_values[2]

benchdamic_results <- read.table(args$results_table, sep='\t', header=T, check.names=F)
results_mats <- list()
for (tool in unique(benchdamic_results$Tool)) {
    results_mats[[tool]] <- benchdamic_results[benchdamic_results$Tool==tool,]
}

for (tool in names(results_mats)) {
    pdf(paste(args$out_dir, "/volcano_plot_", tool, "_", var, "_rawP.pdf", sep=""), width=10, height=8)
    p <- differential_volcano_plot(results_mats[[tool]], valPos, valNeg, args$string_clean_level, args$label_level, args$include_labels)
    print(p)
    dev.off()
}
