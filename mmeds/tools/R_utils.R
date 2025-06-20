library(stringr)
library(tidyverse)
library(qiime2R)

clean_taxa_string <- function(raw_taxa, strict=T, no_reps=F) {
    # Takes in a character vector of taxonomic strings and attempts to coerce them into a 'clean', unified format such that all in the output are unique.
    #   e.g. '(p) Bacteroidota', '(g) Blautia', 'Bifidobacterium longum', 'Prevotella copri clade A', 'Prevotella copri clade F'.
    #   Will include more of the original annotation if strict=F, used recursively to enforce uniqueness.
    taxa_strs <- list()
    repeats <- list()
    for (raw in raw_taxa) {
        # First check for strings that are special cases
        if (raw %in% c("unclassified", "not_reported")) {
          taxa_strs <- append(taxa_strs, raw)
          next
        }
        is_virus <- grepl("virus", raw, ignore.case = T)
        is_uncharacterized_spp <- grepl("sp\\.|sp_|str\\.|str_", raw, ignore.case = T)
        is_unclassified <- grepl("unclassified|not_reported", raw, ignore.case = T)
        is_special_case <- ( is_virus | is_uncharacterized_spp | is_unclassified )

        # Clean "." and "'" characters that will affect the splitting into components
        raw <- str_replace_all(raw, "sp\\.", "sp")
        raw <- str_replace_all(raw, "str\\.", "str")
        raw <- str_replace_all(raw, "sp__", "sp_")
        raw <- str_replace_all(raw, "str__", "str_")
        raw <- str_replace_all(raw, "'", "")
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
                    taxa_str <- paste(genus_split[1:length(genus_split)], paste(lvl_split[anno_start:length(lvl_split)], collapse=' '))
                } else {
                    taxa_str <- paste(lvl_split[anno_start:length(lvl_split)], collapse=' ')
                }
            } else {
                taxa_str <- paste("(", lvl_split[1], ") ", paste(lvl_split[anno_start:length(lvl_split)], collapse=' '), sep="")
            }
        }

        if (taxa_str %in% taxa_strs & !taxa_str %in% repeats) {
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
    features<-as.data.frame(make_percent(features), check.names=F)

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


