library(argparser)

parser <- arg_parser("parse arguments", hide.opts=TRUE)
parser <- add_argument(parser, "feature-table", nargs=1, help="Input feature table")
parser <- add_argument(parser, "metadata-file", nargs=1, help="Metadata for feature table")
parser <- add_argument(parser, "output-file", nargs=1, help="Taxa barplot output")
parser <- add_argument(parser, "--category", help="Optional metadata category by which to separate plot sections")
parser <- add_argument(parser, "--sort", default="top", help="Options for sorting of columns. Choose from ['top' (default), 'all', 'dominant']")
parser <- add_argument(parser, "--colors", default=1, help="Options for ordering of colorscheme. Choose from [1, 2, 3]")
parser <- add_argument(parser, "--width", default=15, help="Width in inches of the resulting plot")
parser <- add_argument(parser, "--no-string-clean", flag=TRUE, help="If set, no processing will be done on row labels")

args <- parse_args(parser)

library(ggplot2)
library(dplyr)
library(tidyverse)
library(ggpubr)
library(stringr)
library(this.path)
library(qiime2R)

# MMEDS R utils
source(paste(this.dir(), "R_utils.R", sep="/"))

# Prevents Rplots.pdf being generated in working dir
pdf(NULL)

bkg <- theme_q2r() +
    theme(axis.text.x = element_text(size = 10, color = "black", face = "bold")) +
    theme(axis.text.x = element_text(angle=90, vjust = 0.5, hjust = 1)) +
    theme(axis.title.x = element_blank()) +
    theme(axis.text.y = element_text(size = 10, color = "black")) +
    theme(axis.title.y = element_text(size = 14, face = "bold", color = "black")) +
    theme(axis.title.y = element_text(margin = unit(c(0,4,0,0), "mm"))) +
    theme(legend.position = "right") +
    theme(legend.text = element_text(size = 7)) +
    theme(legend.key.size = unit(0.4, 'cm')) +
    theme(panel.border = element_rect(color = "black", fill = NA, size = 1)) +
    theme(panel.spacing.x=unit(1, "lines")) +
    theme(strip.text = element_text(size = 8, face = "bold", color = "black")) +
    theme(plot.title = element_text(size=14, color= "black", face ="bold")) +
    theme(plot.title = element_text(hjust = 0.5)) +
    theme(axis.text.x = element_blank(), axis.ticks.x = element_blank())

# Multiple orderings of color scheme
col1 <- c("#DDDDDD","#C4C4C4","#acacac","#909090","#757575","#191919","#720510","#a40818","#bf2131","#C62702","#DD2C03","#FE7926","#fdb529","#F3CE5A","#F8DE7E","#394833", 
          "#196919","#528652","#8caf7c","#b6d7a8","#bc7e9e","#A55780","#8f2e61","#870047","#6E1945","#022f59","#005496","#1075b7","#6ea1ca","#b3cde0","#D1E1EC")

col2 <- c("#DDDDDD","#720510","#fdb529","#8caf7c","#6E1945","#D1E1EC","#191919","#FE7926","#528652","#870047","#b3cde0","#757575","#DD2C03","#196919","#8f2e61","#6ea1ca",
          "#909090","#C62702","#394833","#A55780","#1075b7","#acacac","#bf2131","#F8DE7E","#bc7e9e","#005496","#C4C4C4","#a40818","#F3CE5A","#b6d7a8","#005496")

col3 <- col1[c(1, 6, 11, 16, 21, 26, 31, 5, 10, 15, 20, 25, 30, 4, 9, 14, 19, 24, 29, 3, 8, 13, 18, 23, 28, 2, 7, 12, 17, 22, 27)]

if (args$colors == 1) {
    selected_col <- col1 
} else if (args$colors == 2) {
    selected_col <- col2 
} else {
    selected_col <- col3
}

if (grepl("qza$", args$feature_table)) {
    data <- read_qza(args$feature_table)$data
} else {
    data <- read.table(args$feature_table, header = T, sep = "\t", row.names = 1, check.names = F)
}
metadata <- read_q2metadata(args$metadata_file)

if (!args$no_string_clean) {
    rownames(data) <- clean_taxa_string(rownames(data), no_reps=T)
}

p <- taxa_barplot(data, metadata, category = args$category, ntoplot = 30, sort = args$sort) +
      ylab("Relative abundance (%)") + guides(fill = guide_legend(ncol = 1)) + scale_fill_manual(values = rev(selected_col)) + bkg
plot(p)
ggsave(args$output_file, height=6, width=args$width, units='in')

