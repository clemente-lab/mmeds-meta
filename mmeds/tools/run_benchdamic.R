library(argparser)

parser <- arg_parser("parse arguments", hide.opts=TRUE)
parser <- add_argument(parser, "feature-table", nargs=1, help="Input feature table")
parser <- add_argument(parser, "metadata-file", nargs=1, help="Metadata for feature table")
parser <- add_argument(parser, "metadata-column", nargs=1, help="Metadata category on which to perform analysis")
parser <- add_argument(parser, "metadata-values", nargs=2, help="Two comma-separated values in the metadata category \
                                                                 that will be differentiated, positive value first")
parser <- add_argument(parser, "out-dir", nargs=1, help="Directory for outputting results")
parser <- add_argument(parser, "--string-clean-level", default=2, help="0=No string cleaning; 1=Non-strict string cleaning; 2=Strict string cleaning;")
parser <- add_argument(parser, "--faster", flag=T, help="Only run quicker benchdamic DAA methods (currently LinDA, MaAsLin2)")
parser <- add_argument(parser, "--label-level", default=2, help="0=Only label features that match args from --include-labels; \
                                                                 1=Label matching args and all significant above qval thresh; \
                                                                 2=Label matching args and all significant above pval thresh")
parser <- add_argument(parser, "--include-labels", nargs=Inf, help="Any number of comma-separated values to use with grep \
                                                                    to determine which features to label in resulting plots")

args <- parse_args(parser)
print(args)

library(benchdamic)
library(qiime2R)
library(phyloseq)
library(this.path)
library(stringr)

# MMEDS R utils
source(paste(this.dir(), "R_utils.R", sep="/"))

# Prevents Rplots.pdf being generated in working dir
pdf(NULL)

var <- args$metadata_column
valPos <- args$metadata_values[1]
valNeg <- args$metadata_values[2]
var_comb <- paste(var, valNeg, sep="")
form_str <- paste("~", var)
form <- formula(form_str)

phyloseq_data_obj <- qza_to_phyloseq(
    features=args$feature_table,
    metadata=args$metadata_file
)

q2_features <- as.data.frame(t(make_proportion(read_qza(args$feature_table)$data)), check.names=F)
features_vec <- colnames(q2_features)
features_vec <- str_replace_all(features_vec, ";", "\\.")
features_vec <- str_replace_all(features_vec, " - ", "-")
features_vec <- str_replace_all(features_vec, " \\/ ", "_")
features_vec <- str_replace_all(features_vec, " ", "_")
features_vec <- str_replace_all(features_vec, "\\|", "\\.")
features_vec <- str_replace_all(features_vec, ",|\\(|\\)|\\:", "")
colnames(q2_features) <- features_vec
q2_features <- rownames_to_column(q2_features, var="SampleID")
q2_metadata <- read_q2metadata(args$metadata_file)
q2_data_obj <- merge(q2_metadata, q2_features, by="SampleID", suffixes=c("", ".2"))
foldchange_df <- get_fold_change(q2_data_obj, var, c(valPos, valNeg), features_vec)

subset_text <- paste(var, " %in% c('", valPos, "', '", valNeg, "')", sep="")

phyloseq_data_obj <- phyloseq_data_obj %>% subset_samples(
    eval(parse(text=subset_text))
)

phyloseq_data_obj <- phyloseq_data_obj %>% transform_sample_counts(
    function(x) {as.integer(x)}
)

#norms <- setNormalizations(
#  fun = c("norm_edgeR", "norm_DESeq2", "norm_CSS"),
#  method = c("TMM", "poscounts", "CSS")
#)
#phyloseq_data_obj <- runNormalizations(norms, phyloseq_data_obj)

rownames(otu_table(phyloseq_data_obj)) <- features_vec

run_ALDEx2 <- set_ALDEx2(
  pseudo_count = FALSE,
  design = var,
  mc.samples = 1024,
  test = "wilcox",
  paired.test = FALSE,
  denom = "all",
  contrast = c(var, valPos, valNeg),
  expand = TRUE
)

run_ANCOMBC <- set_ANCOM(
  pseudo_count = FALSE,
  fix_formula = var,
  contrast = c(var, valPos, valNeg),
  BC = TRUE,
  expand = TRUE
)

run_LinDA <- set_linda(
  formula = form_str,
  contrast = c(var, valPos, valNeg),
  is.winsor = TRUE,
  zero.handling = "imputation",
  alpha = 0.05,
  expand = TRUE
)

run_Maaslin2 <- set_Maaslin2(
  normalization = "CLR",
  transform = "NONE",
  analysis_method = "LM",
  fixed_effects = var,
  contrast = c(var, valPos, valNeg),
  expand = TRUE
)

run_methods <- c(run_ALDEx2, run_ANCOMBC, run_LinDA, run_Maaslin2)
if (args$faster) {
    run_methods <- c(run_LinDA, run_Maaslin2)
}
benchdamic_results <- runDA(run_methods, phyloseq_data_obj)

if (args$faster) {
    results_mats <- list(
        "LinDA"=as.data.frame(benchdamic_results$linda.win0.03.imputation$pValMat),
        "MaAsLin2"=as.data.frame(benchdamic_results$Maaslin2.CLRnorm.NONEtrans.LM$pValMat)
    )
} else {
    results_mats <- list(
        "ALDEx2"=as.data.frame(benchdamic_results$ALDEx2.all.wilcox.unpaired$pValMat),
        "ANCOM-BC"=as.data.frame(benchdamic_results$ANCOM.BC$pValMat),
        "LinDA"=as.data.frame(benchdamic_results$linda.win0.03.imputation$pValMat),
        "MaAsLin2"=as.data.frame(benchdamic_results$Maaslin2.CLRnorm.NONEtrans.LM$pValMat)
    )
}

for (tool in names(results_mats)) {
    results_mats[[tool]] <- rownames_to_column(results_mats[[tool]], var="feature")
    results_mats[[tool]] <- merge(results_mats[[tool]], foldchange_df, by="feature")
    results_mats[[tool]]$Tool <- tool
}

if (!dir.exists(args$out_dir)) {
    dir.create(args$out_dir)
}

out_table <- results_mats[[names(results_mats)[1]]]
for (i in 2:length(names(results_mats))) {
    out_table <- rbind(out_table, results_mats[[names(results_mats)[i]]])
}
write.table(out_table, paste(args$out_dir, "/benchdamic_results_table_", var, ".tsv", sep=""), sep='\t', row.names=F, quote=F)

for (tool in names(results_mats)) {
    pdf(paste(args$out_dir, "/volcano_plot_", tool, "_", var, "_rawP.pdf", sep=""), width=10, height=8)
    p <- differential_volcano_plot(results_mats[[tool]], valPos, valNeg, args$string_clean_level, args$label_level, args$include_labels)
    print(p)
    dev.off()
}
