library(argparser)

parser <- arg_parser("parse arguments", hide.opts=TRUE)
parser <- add_argument(parser, "results-table", nargs=1, help="LEfSe Results Table")
parser <- add_argument(parser, "output-file", nargs=1, help="LEfSe plot output")
parser <- add_argument(parser, "--row-max", nargs=1, help="Will filter table down to the top {row-max} strengths", default=NA, type='integer')
parser <- add_argument(parser, "--match-string", nargs=1, help="Only plot features that contain a match with a string", default=NA)
parser <- add_argument(parser, "--strict", flag=TRUE, help="Analysis run strictly on more than two classes, allow for this")
parser <- add_argument(parser, "--no-string-clean", flag=TRUE, help="If set, no processing will be done on row labels")

args <- parse_args(parser)

library(ggplot2)
library(dplyr)
library(tidyverse)
library(ggpubr)
library(stringr)
library(this.path)

# MMEDS R utils
source(paste(this.dir(), "R_utils.R", sep="/"))


# Prevents Rplots.pdf being generated in working dir
pdf(NULL)

bkg <-
    theme(axis.text.x = element_text(size = 10, color = "black")) +
    theme(axis.text.x = element_text(angle=90, vjust = 0.5, hjust = 1)) +
    theme(axis.title.x = element_text(margin = unit(c(0,0,4,0), "mm"))) +
    theme(axis.title.x = element_text(size = 10, color = "black")) +
    theme(axis.text.y = element_text(size = 8, color = "black")) +
    theme(axis.title.y = element_text(size = 10, color = "black")) +
    theme(axis.title.y = element_text(margin = unit(c(0,4,0,0), "mm"))) +
    theme(legend.position = "right") +
    theme(legend.text = element_text(size = 8)) +
    theme(legend.key.size = unit(0.6, 'cm')) +
    theme(panel.grid.major = element_blank()) +
    theme(panel.grid.minor = element_blank()) +
    theme(panel.background = element_blank()) +
    theme(axis.line = element_line(colour = "black")) +
    theme(plot.title = element_text(size=, color= "black", face ="bold")) +
    theme(plot.title = element_text(hjust = 0.5)) +
    theme(plot.subtitle = element_text(size=9, color= "black"))

colors <- c("blue3", "#E68800", 'green4', 'pink', 'brown', 'grey')

data <-read.table(args$results_table, header = T, sep = "\t")

plot_data <- subset(data, !is.na(data$LDA))
if (!is.na(args$match_string)) {
    plot_data <- plot_data[grepl(args$match_string, plot_data$RawTaxa, ignore.case=T),]
}

if (nrow(plot_data) == 0) {
    pdf(args$output_file, height=5, width=5)
    plot.new()
    text(0.45, 0.5, "No Significant Results")
    dev.off()
} else {
    plot_data$Group <- as.character(plot_data$Group)
    if (args$no_string_clean) {
        plot_data$Taxa <- plot_data$RawTaxa
    } else {
        plot_data$Taxa <- clean_taxa_string(plot_data$RawTaxa)
    }

    plot_data <- plot_data[order(plot_data$Group),]
    if (!args$strict && length(unique(plot_data$Group)) > 1) {
        plot_data[plot_data$Group == unique(plot_data$Group)[1],]$LDA <- -1 * plot_data[plot_data$Group == unique(plot_data$Group)[1],]$LDA
    }
    plot_data <- plot_data[!duplicated(plot_data$Taxa),]

    if (!is.na(args$row_max) && nrow(plot_data) > args$row_max) {
        plot_data <- plot_data[order(-abs(plot_data$LDA)),][1:args$row_max,]
        plot_data <- plot_data[order(plot_data$Group),]
    }

    plot_width <- (max(nchar(plot_data$Taxa)) + max(nchar(plot_data$Group)))*30 + 1000
    plot_height <- nrow(plot_data)*50 + 400
    p <- ggbarplot(plot_data, x="Taxa", y="LDA", fill="Group", width= 1, color = "white", sort.val = "asc", sort.by.groups=TRUE) + 
        labs(x = "", y = "LDA score", fill="Group") + coord_flip() + bkg +
        scale_fill_manual(values=colors)
    plot(p)
    ggsave(args$output_file, width=plot_width, height=plot_height, units = 'px', limitsize = FALSE)
}
