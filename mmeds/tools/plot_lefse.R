library(argparser)

parser <- arg_parser("parse arguments", hide.opts=TRUE)
parser <- add_argument(parser, "results-table", nargs=1, help="LEfSe Results Table")
parser <- add_argument(parser, "output-file", nargs=1, help="LEfSe plot output")
parser <- add_argument(parser, "--strict", flag=TRUE, help="Analysis run strictly on more than two classes, allow for this")

args <- parse_args(parser)

library(ggplot2)
library(dplyr)
library(tidyverse)
library(ggpubr)
library(stringr)

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
if (nrow(plot_data) == 0) {
    pdf(args$output_file, height=5, width=5)
    plot.new()
    text(0.45, 0.5, "No Significant Results")
    dev.off()
} else {
    taxa_strs <- list()
    for (raw in plot_data$RawTaxa) {
        split <- as.character(unlist(str_split(raw, "\\.")))
        i <- length(split)
        blanks <- 0
        while (i > 0) {
            if (split[i] == "__" | str_sub(split[i], start=-2) == "__") {
                blanks <- blanks + 1
                split <- split[1:i-1]
            }
            else {
                break
            }
            i <- i - 1
        }

        if (length(split) == 1) {
            taxa_str <- split[1]
        }
        else {
            taxa_str <- paste(split[length(split)-1], split[length(split)])
        }

        if (blanks > 0) {
            for (i in 1:blanks) {
                taxa_str <- paste(taxa_str, "__uncl.", sep="")
            }
        }
        taxa_strs <- append(taxa_strs, taxa_str)
    }

    plot_data$Taxa <- as.character(taxa_strs)
    plot_data <- plot_data[order(plot_data$Group),]
    if (!args$strict) {
        plot_data[plot_data$Group == unique(plot_data$Group)[1],]$LDA <- -1 * plot_data[plot_data$Group == unique(plot_data$Group)[1],]$LDA
    }
    plot_data <- plot_data[!duplicated(plot_data$Taxa),]

    plot_width <- (max(nchar(plot_data$Taxa)) + max(nchar(plot_data$Group)))*30 + 1000
    plot_height <- nrow(plot_data)*50 + 400
    p <- ggbarplot(plot_data, x="Taxa", y="LDA", fill="Group", width= 1, color = "white", sort.val = "asc", sort.by.groups=TRUE) + 
        labs(x = "", y = "LDA score", fill="Group") + coord_flip() + bkg +
        scale_fill_manual(values=colors)
    plot(p)
    ggsave(args$output_file, width=plot_width, height=plot_height, units = 'px', limitsize = FALSE)
}
