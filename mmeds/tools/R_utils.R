library(stringr)

clean_taxa_string <- function(raw_taxa, strict=T) {
    # Takes in a character vector of taxonomic strings and attempts to coerce them into a 'clean', unified format such that all in the output are unique.
    #   e.g. '(p) Bacteroidota', '(g) Blautia', 'Bifidobacterium longum', 'Prevotella copri clade A', 'Prevotella copri clade F'.
    #   Will include more of the original annotation if strict=F, used recursively to enforce uniqueness.
    taxa_strs <- list()
    repeats <- list()
    for (raw in raw_taxa) {
        # First check for strings that are special cases
        is_virus <- grepl("virus", raw, ignore.case = T)
        is_uncharacterized_spp <- grepl("sp\\.|str\\.", raw, ignore.case = T)
        is_special_case <- ( is_virus | is_uncharacterized_spp )

        # Clean "." and "'" characters that will affect the splitting into components
        raw <- str_replace_all(raw, "sp\\.", "sp")
        raw <- str_replace_all(raw, "str\\.", "str")
        raw <- str_replace_all(raw, "'", "")

        # Check if the string contains a viral annotation

        # Split the string components, which may be delimited by ".", "|", or ";"
        split <- as.character(unlist(str_split(raw, "\\.|\\||\\;")))
        i <- length(split)
        blanks <- 0
        has_spp <- str_sub(split[length(split)], 1, 1) == "s"
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

        # Split the most detailed string component further into its sub-levels
        lvl_split <- as.character(unlist(str_split(split[length(split)], "_")))
        i <- length(lvl_split)
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
                # The third and final elements at this point should represent the genus and species
                taxa_str <- paste(lvl_split[3], lvl_split[length(lvl_split)])
            } else {
                # The first element should represent the letter code of the taxa level, and the final element should represent that annotation
                taxa_str <- paste("(", lvl_split[1], ") ", lvl_split[length(lvl_split)], sep="")
            }
        } else {
            # Not running strictly or string is a virus, remove less
            if (has_spp) {
                taxa_str <- paste(lvl_split[3:length(lvl_split)], collapse=' ')
            } else {
                taxa_str <- paste("(", lvl_split[1], ") ", paste(lvl_split[3:length(lvl_split)], collapse=' '), sep="")
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
        if (taxa_out %in% repeats) {
            taxa_out <- clean_taxa_string(raw_taxa[i], strict = F)
        }
        taxa_strs_out <- append(taxa_strs_out, taxa_out)
    }
    return(as.character(taxa_strs))
}

