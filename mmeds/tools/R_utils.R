library(stringr)
library(tidyverse)
library(qiime2R)
library(ggrepel)

clean_taxa_string <- function(raw_taxa, strict=T, no_reps=F) {
    # Takes in a character vector of taxonomic strings and attempts to coerce them into a 'clean', unified format such that all in the output are unique.
    #   e.g. '(p) Bacteroidota', '(g) Blautia', 'Bifidobacterium longum', 'Prevotella copri clade A', 'Prevotella copri clade F'.
    #   Will include more of the original annotation if strict=F, used recursively to enforce uniqueness.
    taxa_strs <- list()
    repeats <- list()
    for (raw in raw_taxa) {
        # First check for strings that are special cases
        if (grepl("not_reported", raw) || raw=="unclassified") {
          taxa_strs <- append(taxa_strs, raw)
          next
        }
        is_virus <- grepl("virus", raw, ignore.case = T)
        is_uncharacterized_spp <- grepl("sp\\.|sp_|str\\.|str_", raw, ignore.case = T)
        is_unclassified <- grepl("unclassified|not_reported", raw, ignore.case = T)
        is_clade <- grepl("_clade_", raw, ignore.case = T)
        is_special_case <- ( is_virus | is_uncharacterized_spp | is_unclassified | is_clade )

        # Clean "." and "'" characters that will affect the splitting into components
        raw <- str_replace_all(raw, "sp\\.", "sp")
        raw <- str_replace_all(raw, "str\\.", "str")
        raw <- str_replace_all(raw, "sp__", "sp_")
        raw <- str_replace_all(raw, "str__", "str_")
        raw <- str_replace_all(raw, "'", "")
        # raw <- str_replace_all(raw, "\\.", "")
        raw <- str_replace_all(raw, "___", "__")
        raw <- str_replace_all(raw, "'", "")
        raw <- str_replace_all(raw, " ", "_")

        # Split the string components, which may be delimited by ".", "|", or ";"
        split <- as.character(unlist(str_split(raw, "\\.|\\||\\;")))
        i <- length(split)
        blanks <- 0
        while (i > 0) {
            # Trim off unclassified components, and determine whether the string is classified at the species level
            if (!split[i] == "__" & str_sub(split[i], start=-2) == "__") {
                blanks <- blanks + 1
                split <- split[1:i-1]
                has_spp <- F
            } else if (split[i] == "__") {
                split <- split[1:i-1]
                has_spp <- F
            # } else if (grepl("s1__|s2__|t__", split[i])) {
            # How to handle strain-level annotations?
            } else {
                break
            }
            i <- i - 1
        }
        has_spp <- str_sub(split[length(split)], 1, 1) == "s"

        # Split the most detailed string component further into its sub-levels
        lvl_split <- as.character(unlist(str_split(split[length(split)], "_")))
        i <- length(lvl_split)
        anno_start <- 3
        while (anno_start <= length(split) & lvl_split[anno_start] == "") {
            anno_start <- anno_start + 1
        }
        if (strict & !is_special_case) {
            # Running strictly, remove more
            while(i > 0) {
                # Remove numeric components or short modifiers to species annotations
                if (grepl("^[0-9]+$", lvl_split[i]) | (str_length(lvl_split[i]) < 4 & !lvl_split[i] %in% c("d", "k", "p", "c", "o", "f", "g"))) {
                    lvl_split <- lvl_split[1:length(lvl_split)-1]
                } else {
                    break
                }
                i <- i - 1
            }

            if (has_spp) {
                if (anno_start == length(lvl_split)) {
                    # Only one string at species level, get genus from previous level
                    genus_split <- as.character(unlist(str_split(split[length(split)-1], "_")))
                    genus <- genus_split[length(genus_split)]
                    if (is.na(genus) || genus == "") {genus <- genus_split[length(genus_split)-1]}
                    taxa_str <- paste(genus, lvl_split[length(lvl_split)])
                } else {
                    # The third and final elements at this point should represent the genus and species
                    taxa_str <- paste(lvl_split[anno_start], lvl_split[length(lvl_split)])
                }
            } else if (anno_start == length(lvl_split)) {
                # The first element should represent the letter code of the taxa level, and the final element should represent that annotation
                taxa_str <- paste("(", lvl_split[1], ") ", lvl_split[length(lvl_split)], sep="")
            } else {
                # Multiple tokens in the annotation level
                taxa_str <- paste("(", lvl_split[1], ") ", paste(lvl_split[anno_start:length(lvl_split)], collapse=' '), sep="")
            }
        } else {
            # Not running strictly or string is a special case, remove less
            if (has_spp) {
                if (anno_start == length(lvl_split)) {
                    # Only one string at species level, get genus from previous level
                    genus_split <- as.character(unlist(str_split(split[length(split)-1], "_")))
                    taxa_str <- paste(genus_split[3:length(genus_split)], paste(lvl_split[anno_start:length(lvl_split)], collapse=' '))
                } else {
                    taxa_str <- paste(lvl_split[anno_start:length(lvl_split)], collapse=' ')
                }
            } else {
                taxa_str <- paste("(", lvl_split[1], ") ", paste(lvl_split[anno_start:length(lvl_split)], collapse=' '), sep="")
            }
        }

        if (taxa_str %in% taxa_strs && !taxa_str %in% repeats) {
            repeats <- append(repeats, taxa_str)
        }
        taxa_strs <- append(taxa_strs, taxa_str)
    }

    taxa_strs_out <- list()
    for (i in 1:length(taxa_strs)) {
        # Recursively rerun non-strictly those taxa strings that were not unique in the set after running strictly
        taxa_out <- taxa_strs[i]
        if (taxa_out %in% repeats || grepl(" NA ", taxa_out)) {
            taxa_out <- clean_taxa_string(raw_taxa[i], strict = F)
        }
        while (no_reps && taxa_out %in% taxa_strs_out) {
            taxa_out <- paste(taxa_out, "_", sep="")
        }
        taxa_strs_out <- append(taxa_strs_out, taxa_out)
    }
    return(as.character(taxa_strs_out))
}

wrap_text <- function(x, chars = 10) {
    # Wrapping function that replaces underscores with spaces
    x <- gsub("_", " ", x)
    stringr::str_wrap(x, chars)
}

taxa_barplot <- function(features, metadata, category, ntoplot, sort="top"){
    # Modified version of taxa_barplot from qiime2R library
    # Takes in a feature table, optional parameters, and outputs the resulting taxa plot

    q2r_palette<-c(
        "blue4",
        "olivedrab",
        "firebrick",
        "gold",
        "darkorchid",
        "steelblue2",
        "chartreuse1",
        "aquamarine",
        "yellow3",
        "coral",
        "grey"
    )

    if(missing(ntoplot) & nrow(features)>10){ntoplot=10} else if (missing(ntoplot)){ntoplot=nrow(features)}
    features <- as.data.frame(make_percent(features), check.names=F)
    features[is.na(features)] <- 0

    if(missing(metadata)){metadata<-data.frame(SampleID=colnames(features))}
    if(!"SampleID" %in% colnames(metadata)){metadata <- metadata %>% rownames_to_column("SampleID")}
    if(!missing(category) && !is.na(category)){
        if(!category %in% colnames(metadata)){message(stop(category, " not found as column in metdata"))}
    }

    plotfeats<-names(sort(rowMeans(features), decreasing = TRUE)[1:ntoplot]) # extract the top N most abundant features on average

    if (sort=="top") {
        sort_by <- c(plotfeats[1])
    } else if (sort %in% c("all", "dominant")) {
        sort_by <- plotfeats
        if (sort=="dominant") {
            plot_features <- features[rownames(features) %in% plotfeats,]
            dominant_taxa <- rownames(plot_features)[apply(plot_features, 2, which.max)]
        }
    } else {
        sort_by <- c(plotfeats[1])
    }

    sort_vec <- rep(NA, ncol(features))
    sort_index <- 1
    for (feat in sort_by) {
        if (sort == "dominant") {
            if (!any(dominant_taxa==feat)) {next}
            sort_feat <- features[,dominant_taxa==feat, drop=F]
            if (ncol(sort_feat)==1) {
                sort_vec[sort_index] <- colnames(sort_feat)[1]
                sort_index <- sort_index + 1
                next
            }
        } else {
            sort_feat <- features
        }

        if (sort_index == 1 | sort == "dominant") {
            sort_feat <- sort_feat[rownames(sort_feat)==feat,]
        } else {
            sort_feat <- sort_feat[rownames(sort_feat)==feat, !colnames(sort_feat) %in% sort_vec[1:(sort_index-1)], drop=F]
        }

        sort_feat <- sort_feat[,order(colSums(sort_feat), decreasing = T), drop=F]
        sort_feat <- sort_feat[,colSums(sort_feat) > 0, drop=F]
        for (n in colnames(sort_feat)) {
            sort_vec[sort_index] <- n
            sort_index <- sort_index + 1
        }
    }

    sort_feat <- features[,!colnames(features) %in% sort_vec[1:(sort_index-1)], drop=F]
    name_index <- 1
    if (sort=="dominant" & sort_index < ncol(features)) {
        remainder_feat <- sort_feat[!rownames(sort_feat) %in% plotfeats,]
        remainder_feat <- remainder_feat[,order(colSums(remainder_feat))]
        for (n in colnames(remainder_feat)) {
            sort_vec[sort_index] <- n
            sort_index <- sort_index + 1
        }
    }
    while (sort_index <= ncol(features)) {
        sort_vec[sort_index] <- colnames(sort_feat)[name_index]
        sort_index <- sort_index + 1
        name_index <- name_index + 1
    }

    suppressMessages(
        suppressWarnings(
            fplot<-
                features %>%
                as.data.frame() %>%
                rownames_to_column(var="Taxon") %>%
                gather(-Taxon, key="SampleID", value="Abundance") %>%
                mutate(Taxon=if_else(Taxon %in% plotfeats, Taxon, "Remainder")) %>%
                group_by(Taxon, SampleID) %>%
                summarize(Abundance=sum(Abundance)) %>%
                ungroup() %>%
                mutate(Taxon=factor(Taxon, levels=rev(c(plotfeats, "Remainder")))) %>%
                left_join(metadata)
        )
    )
    feature_order <- c(names(rowMeans(features)[order(rowMeans(features), decreasing=T)][1:ntoplot]), 'Remainder')
    fplot$Taxon <- factor(fplot$Taxon, levels=feature_order)

    bplot<-
        ggplot(fplot, aes(x=factor(SampleID, levels=sort_vec), y=Abundance, fill=Taxon)) +
        geom_bar(stat="identity") +
        theme_q2r() +
        theme(axis.text.x = element_text(angle=45, hjust=1)) +
        coord_cartesian(expand=FALSE) +
        xlab("Sample") +
        ylab("Abundance")

    if(ntoplot<=10){bplot<-bplot+scale_fill_manual(values=rev(q2r_palette), name="")}

    if(!missing(category) && !is.na(category)){bplot<-bplot + facet_grid(~get(category), scales="free_x", space="free", labeller = as_labeller(wrap_text))}

    return(bplot)
}

get_fold_change <- function(data, column, column_labels, features) {
    # Given a set of features (e.g. taxa, pathways) and a two-way comparison between groups,
    #   return dataframe with one column of features and one column of groupwise log2FoldChange
    features_df <- data[, features]
    features_df[] <- lapply(features_df, function(x) as.numeric(as.character(x)))
    min_nonzero <- min(features_df[features_df!=0], na.rm=T)
    pseudo <- 10^floor(log10(min_nonzero))

    folds <- c()
    group1 <- data[data[[column]]==column_labels[1] & !is.na(data[[column]]),]
    group2 <- data[data[[column]]==column_labels[2] & !is.na(data[[column]]),]
    for (f in features) {
        set1 <- group1[[f]]
        set2 <- group2[[f]]
        fold <- mean(log2(set1+pseudo)) - mean(log2(set2+pseudo))
        folds <- c(folds, fold)
    }

    fold_df <- data.frame(
        feature=features,
        log2FC=folds
    )
    return(fold_df)
}

get_qval_on_pval_scale <- function(plot_mat, qval_thresh) {
    plot_mat_qval_signif <- plot_mat[!is.na(plot_mat$adjP) & plot_mat$adjP < qval_thresh,]
    plot_mat_qval_signif <- plot_mat_qval_signif[order(-plot_mat_qval_signif$adjP),]
    plot_mat_qval_not_signif <- plot_mat[!is.na(plot_mat$adjP) & plot_mat$adjP >= qval_thresh,]
    plot_mat_qval_not_signif <- plot_mat_qval_not_signif[order(plot_mat_qval_not_signif$adjP),]

    if (nrow(plot_mat_qval_signif)==0) {
        return ((min(plot_mat_qval_not_signif$rawP) / 2))
    }

    pval_high <- plot_mat_qval_not_signif$rawP[1]
    pval_low <- plot_mat_qval_signif$rawP[1]
    qval_on_pval_scale <- mean(c(pval_high, pval_low))
    return (qval_on_pval_scale)
}

differential_volcano_plot <- function(plot_mat, valPos, valNeg, string_clean_level=2, label_level=2, include_labels=NA) {
    no_inf <- plot_mat[abs(plot_mat$log2FC)!=Inf & !is.na(plot_mat$rawP),]
    max_x <- max(abs(min(no_inf$log2FC)), max(no_inf$log2FC))
    max_x <- max_x * 1.05
    if (Inf %in% plot_mat$log2FC) {plot_mat[plot_mat$log2FC==Inf,]$log2FC <- max_x}
    if (-Inf %in% plot_mat$log2FC) {plot_mat[plot_mat$log2FC==-Inf,]$log2FC <- -max_x}

    pval_thresh <- 0.05
    qval_thresh <- 0.1
    qval_thresh_as_pval <- min(pval_thresh, get_qval_on_pval_scale(plot_mat, qval_thresh))

    plot_mat$label <- ""
    if (label_level==2) {label_thresh <- pval_thresh}
    else if (label_level==1) {label_thresh <- qval_thresh_as_pval} 
    else {label_thresh <- 0}
    if (!all(is.na(include_labels)) && (length(include_labels)>0)) {
        label_grep_pattern <- paste(include_labels, collapse="|")
        print(label_grep_pattern)
        label_rows <- c(!is.na(plot_mat$rawP) & (plot_mat$rawP < label_thresh | grepl(label_grep_pattern, plot_mat$feature, ignore.case=T)))
    } else {
        label_rows <- c(!is.na(plot_mat$rawP) & plot_mat$rawP < label_thresh)
    }
    if (nrow(plot_mat[label_rows,]) > 0) {
        if (string_clean_level > 0) {
            plot_mat[label_rows,]$label <- clean_taxa_string(plot_mat[label_rows,]$feature, strict=(string_clean_level==2))
        } else {
            plot_mat[label_rows,]$label <- plot_mat[label_rows,]$feature
        }
    }

    plot_mat$signif <- "0"
    rows_raw <- c(!is.na(plot_mat$rawP) & plot_mat$rawP<pval_thresh)
    pos_rows_adj <- c(!is.na(plot_mat$rawP) & plot_mat$rawP<qval_thresh_as_pval & !is.na(plot_mat$log2FC) & plot_mat$log2FC>0)
    neg_rows_adj <- c(!is.na(plot_mat$rawP) & plot_mat$rawP<qval_thresh_as_pval & !is.na(plot_mat$log2FC) & plot_mat$log2FC<0)
    if (nrow(plot_mat[c(rows_raw),]) > 0) {
        plot_mat[rows_raw,]$signif <- "1"
    }
    if (nrow(plot_mat[pos_rows_adj,]) > 0) {
        plot_mat[pos_rows_adj,]$signif <- "2"
    }
    if (nrow(plot_mat[neg_rows_adj,]) > 0) {
        plot_mat[neg_rows_adj,]$signif <- "3"
    }

    p <- ggplot(plot_mat, aes(x=log2FC, y=-log2(rawP), color=factor(signif, levels=c("0", "1", "2", "3")))) +
        geom_hline(yintercept=-log2(pval_thresh), linewidth=0.3, color="grey20", linetype = "dashed") +
        geom_hline(yintercept=-log2(qval_thresh_as_pval), linewidth=0.3, color="grey20", linetype = "dashed") +
        theme_classic() + theme(legend.position="none") + labs(x=paste(valNeg, "   <-   log2FC   ->   ", valPos)) +
        geom_text_repel(aes(label=label), color="black", force=5, max.overlaps=100, force_pull=0.1, size=3, min.segment.length=0.2) +
        scale_color_manual(values=c("0"="grey60", "1"="grey30", "2"="red3", "3"="cyan3")) + xlim(-max_x, max_x) + geom_point()
    return(p)
}

