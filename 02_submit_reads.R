##############################################################################
## SUBMIT READS - build the ena-bulk-webincli spreadsheet for paired-end reads
## Author: Maria Kamouyiaros @NHMUK (updated by Dan Parsons @NHMUK)
##
## Joins a samplesheet of FASTQ paths to the ENA Samples Report (registered
## samples) by sample alias, checks every FASTQ file, and writes the TSV used
## by ena-bulk-webincli (https://github.com/enasequence/ena-bulk-webincli).
##
## Inputs
##   samplesheet     CSV: sample_alias, uploaded file 1, uploaded file 2
##                   (optional: library_description)
##                   May contain samples that are not registered yet.
##                   A sample may have several rows (several read sets).
##   samples_report  CSV downloaded from Webin (Samples > Samples Report),
##                   with the sample accession ('id') and alias ('alias')
##
## FASTQ paths
##   bulk_webincli.py passes its -d directory to Webin-CLI as -inputDir, and
##   the paths in the TSV must be relative to it. Absolute paths in the
##   samplesheet are rewritten relative to upload_dir (using ../ where
##   needed), so set upload_dir to the directory you will give to -d.
##
## Several read sets for one sample
##   Each different pair of FASTQs for a sample alias becomes its own
##   experiment: BGE_<alias>_1, BGE_<alias>_2, ... (numbered in samplesheet
##   order). Samples with one read set keep BGE_<alias>. Rows with the same
##   alias AND the same two files are exact duplicates: they are reported as
##   problems and not submitted.
##
## Outputs (prefix set by output_prefix)
##   <prefix>.tsv                     submission spreadsheet for bulk_webincli.py
##   <prefix>_pending.csv             samplesheet rows not in the Samples Report
##                                    (not registered yet) - submit later
##   <prefix>_file_problems.csv       read sets left out because of a FASTQ
##                                    problem or an exact duplicate row
##   <prefix>_duplicate_rows.csv      samples with more than one samplesheet
##                                    row, and the experiment names they get
##   <prefix>_registered_no_reads.csv samples in the Samples Report with no
##                                    samplesheet row (for information)
##
## Run with:  Rscript 02_submit_reads.R
## Base R only - no packages needed.
##############################################################################

# ---------------------------------------------------------------------------
# Settings - edit these
# ---------------------------------------------------------------------------
samplesheet_file    <- "/home/dparsons/projects/nhm/museomix/BGE/ena_submission/ena-read-upload/ena_read_upload/non_BSNHM_skims/read_upload/samplesheets/combined_samplesheet.csv"
samples_report_file <- "/home/dparsons/projects/nhm/museomix/BGE/ena_submission/ena-read-upload/ena_read_upload/non_BSNHM_skims/sample_reg/nonBSNHM_BGE_sample_reg-2026-11-19.csv"
output_prefix       <- "read_submission"

# Parent directory of the FASTQ files: the same directory given to
# bulk_webincli.py with -d. Paths in the samplesheet are relative to it
# (absolute paths are used as they are).
upload_dir <- "/home/dparsons/projects/nhm/museomix/BGE/seq_data/"

study_accession       <- "PRJEB78703"
experiment_prefix     <- "BGE_"          # experiment_name = prefix + sample alias
sequencing_platform   <- "ILLUMINA"       # ENA permitted values, e.g. ILLUMINA
sequencing_instrument <- "Illumina NovaSeq X" # e.g. "Illumina NovaSeq 6000"
library_source        <- "GENOMIC"
library_selection     <- "RANDOM"
library_strategy      <- "WGS"
# Used when the samplesheet has no library_description column, or it is empty
default_library_description <- "BGE genome skim, paired-end"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# Normalise a column name: lower case, spaces/dots/underscores removed
norm_name <- function(x) gsub("[^a-z0-9]", "", tolower(x))

# Find a column by any of several accepted names (ignoring case and separators)
find_col <- function(df, candidates, file_label, required = TRUE) {
  hit <- names(df)[match(norm_name(candidates), norm_name(names(df)))]
  hit <- hit[!is.na(hit)]
  if (length(hit) == 0) {
    if (required) stop(sprintf("%s has no column called any of: %s. Columns found: %s",
                               file_label, paste(candidates, collapse = ", "),
                               paste(names(df), collapse = ", ")), call. = FALSE)
    return(NA_character_)
  }
  hit[1]
}

clean <- function(x) trimws(ifelse(is.na(x), "", as.character(x)))

split_path <- function(p) { parts <- strsplit(p, "/", fixed = TRUE)[[1]]; parts[parts != ""] }

# Rewrite absolute paths relative to upload_dir. The directory part of each
# path is resolved (symlinks, .., //) but the file name is kept as written.
# Relative and empty paths are returned unchanged.
upload_dir_abs <- normalizePath(upload_dir, mustWork = FALSE)
base_parts <- split_path(upload_dir_abs)
dir_cache <- new.env()
relativise <- function(paths) {
  vapply(paths, function(p) {
    if (!grepl("^/", p)) return(p)
    d <- dirname(p)
    nd <- dir_cache[[d]]
    if (is.null(nd)) { nd <- normalizePath(d, mustWork = FALSE); assign(d, nd, envir = dir_cache) }
    parts <- c(split_path(nd), basename(p))
    n <- 0
    while (n < min(length(parts) - 1, length(base_parts)) && parts[n + 1] == base_parts[n + 1])
      n <- n + 1
    paste(c(rep("..", length(base_parts) - n), parts[-seq_len(n)]), collapse = "/")
  }, character(1), USE.NAMES = FALSE)
}

# Check one FASTQ file; returns "" if fine, otherwise the problem.
# path is relative to upload_dir; shown is the path as written in the samplesheet
check_fastq <- function(path, shown) {
  if (path == "") return("no path given")
  full <- if (grepl("^/", path)) path else file.path(upload_dir, path)
  if (!file.exists(full)) return(paste("file not found:", shown))
  if (dir.exists(full)) return(paste("path is a directory:", shown))
  if (file.size(full) == 0) return(paste("file is empty:", shown))
  if (!grepl("\\.gz$", path)) return(paste("not a .gz file name:", shown))
  con <- file(full, "rb"); magic <- readBin(con, "raw", n = 2); close(con)
  if (length(magic) < 2 || magic[1] != as.raw(0x1f) || magic[2] != as.raw(0x8b))
    return(paste("not gzip-compressed:", shown))
  ""
}

add_problem <- function(problems, rows, problem) {
  if (nrow(rows) == 0) return(problems)
  rbind(problems, data.frame(sample_alias = rows$.alias, experiment_name = rows$.exp,
                             problem = problem, stringsAsFactors = FALSE))
}

# ---------------------------------------------------------------------------
# Read inputs
# ---------------------------------------------------------------------------
sheet  <- read.csv(samplesheet_file, check.names = FALSE, stringsAsFactors = FALSE,
                   colClasses = "character", na.strings = c("", "NA"))
report <- read.csv(samples_report_file, check.names = FALSE, stringsAsFactors = FALSE,
                   colClasses = "character", na.strings = c("", "NA"))

alias_col <- find_col(sheet, c("sample_alias", "alias"), "samplesheet")
r1_col    <- find_col(sheet, c("uploaded file 1", "uploaded.file.1", "uploaded_file_1"), "samplesheet")
r2_col    <- find_col(sheet, c("uploaded file 2", "uploaded.file.2", "uploaded_file_2"), "samplesheet")
desc_col  <- find_col(sheet, c("library_description"), "samplesheet", required = FALSE)

rep_alias_col <- find_col(report, c("alias", "sample_alias"), "Samples Report")
rep_acc_col   <- find_col(report, c("id", "accession", "sample_accession"), "Samples Report")

sheet$.alias  <- clean(sheet[[alias_col]])
sheet$.r1_in  <- clean(sheet[[r1_col]])
sheet$.r2_in  <- clean(sheet[[r2_col]])
sheet$.desc   <- if (is.na(desc_col)) "" else clean(sheet[[desc_col]])
sheet$.desc[sheet$.desc == ""] <- default_library_description
sheet <- sheet[sheet$.alias != "", ]
all_sheet_aliases <- unique(sheet$.alias)

report_alias <- clean(report[[rep_alias_col]])
report_acc   <- clean(report[[rep_acc_col]])
accession_by_alias <- setNames(report_acc, report_alias)
accession_by_alias <- accession_by_alias[!duplicated(names(accession_by_alias))]

cat(sprintf("Samplesheet: %d rows | Samples Report: %d registered samples\n",
            nrow(sheet), length(accession_by_alias)))

# ---------------------------------------------------------------------------
# Paths relative to upload_dir
# ---------------------------------------------------------------------------
sheet$.r1 <- relativise(sheet$.r1_in)
sheet$.r2 <- relativise(sheet$.r2_in)
was_abs   <- grepl("^/", c(sheet$.r1_in, sheet$.r2_in))
n_abs     <- sum(was_abs)

# ---------------------------------------------------------------------------
# Read sets: number them per sample, find exact duplicate rows
# ---------------------------------------------------------------------------
sheet$.key   <- paste(sheet$.alias, sheet$.r1, sheet$.r2, sep = "\r")
first        <- !duplicated(sheet$.key)
set_no_first <- ave(rep(1L, sum(first)), sheet$.alias[first], FUN = seq_along)
sheet$.set   <- set_no_first[match(sheet$.key, sheet$.key[first])]
n_sets       <- tapply(first, sheet$.alias, sum)
n_rows       <- table(sheet$.alias)
sheet$.exp   <- ifelse(n_sets[sheet$.alias] > 1,
                       paste0(experiment_prefix, sheet$.alias, "_", sheet$.set),
                       paste0(experiment_prefix, sheet$.alias))

copies <- table(sheet$.key)[sheet$.key]
exact_dup <- as.vector(copies) > 1

problems <- data.frame(sample_alias = character(), experiment_name = character(),
                       problem = character(), stringsAsFactors = FALSE)
if (any(exact_dup)) {
  dups <- sheet[exact_dup, ]
  problems <- rbind(problems, data.frame(
    sample_alias = dups$.alias, experiment_name = dups$.exp,
    problem = sprintf("identical duplicate row (same sample_alias, uploaded file 1 and uploaded file 2) - appears %d times",
                      as.vector(copies[exact_dup])),
    stringsAsFactors = FALSE))
}

multi <- names(n_rows)[n_rows > 1]
dup_report <- data.frame(
  sample_alias             = multi,
  samplesheet_rows         = as.vector(n_rows[multi]),
  read_sets                = as.vector(n_sets[multi]),
  identical_duplicate_rows = vapply(multi, function(a) sum(exact_dup[sheet$.alias == a]), integer(1)),
  experiment_names         = vapply(multi, function(a) paste(unique(sheet$.exp[sheet$.alias == a]), collapse = ";"),
                                    character(1)),
  stringsAsFactors = FALSE, row.names = NULL)

sheet <- sheet[!exact_dup, ]

# ---------------------------------------------------------------------------
# Registered vs pending
# ---------------------------------------------------------------------------
sheet$.accession <- unname(accession_by_alias[sheet$.alias])
registered <- sheet[!is.na(sheet$.accession), ]
pending    <- sheet[is.na(sheet$.accession), ]

# ---------------------------------------------------------------------------
# FASTQ checks (registered samples only), one read set at a time
# ---------------------------------------------------------------------------
keep <- rep(TRUE, nrow(registered))
for (i in seq_len(nrow(registered))) {
  issues <- c(check_fastq(registered$.r1[i], registered$.r1_in[i]),
              check_fastq(registered$.r2[i], registered$.r2_in[i]))
  if (registered$.r1[i] != "" && registered$.r1[i] == registered$.r2[i])
    issues <- c(issues, "uploaded file 1 and uploaded file 2 are the same file")
  issues <- issues[issues != ""]
  if (length(issues) > 0) {
    keep[i] <- FALSE
    problems <- add_problem(problems, registered[i, ], paste(issues, collapse = "; "))
  }
}
ok <- registered[keep, ]

# Each FASTQ should only be used once across the submission
used <- c(ok$.r1, ok$.r2)
reused <- unique(used[duplicated(used)])
if (length(reused) > 0) {
  bad <- ok$.r1 %in% reused | ok$.r2 %in% reused
  problems <- add_problem(problems, ok[bad, ], "FASTQ file used by more than one read set")
  ok <- ok[!bad, ]
}

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
submission <- data.frame(
  study_accession       = rep(study_accession, nrow(ok)),
  sample_accession      = ok$.accession,
  experiment_name       = ok$.exp,
  sequencing_platform   = rep(sequencing_platform, nrow(ok)),
  sequencing_instrument = rep(sequencing_instrument, nrow(ok)),
  library_source        = rep(library_source, nrow(ok)),
  library_selection     = rep(library_selection, nrow(ok)),
  library_strategy      = rep(library_strategy, nrow(ok)),
  library_description   = ok$.desc,
  "uploaded file 1"     = ok$.r1,
  "uploaded file 2"     = ok$.r2,
  check.names = FALSE, stringsAsFactors = FALSE)
write.table(submission, paste0(output_prefix, ".tsv"), sep = "\t", quote = FALSE,
            row.names = FALSE)

# Pending rows keep the paths as written in the samplesheet, for re-use later
pending_out <- data.frame(sample_alias = pending$.alias,
                          "uploaded file 1" = pending$.r1_in, "uploaded file 2" = pending$.r2_in,
                          check.names = FALSE, stringsAsFactors = FALSE)
write.csv(pending_out, paste0(output_prefix, "_pending.csv"), row.names = FALSE)
write.csv(problems, paste0(output_prefix, "_file_problems.csv"), row.names = FALSE)
write.csv(dup_report, paste0(output_prefix, "_duplicate_rows.csv"), row.names = FALSE)

no_reads <- setdiff(names(accession_by_alias), all_sheet_aliases)
write.csv(data.frame(sample_alias = no_reads,
                     sample_accession = unname(accession_by_alias[no_reads])),
          paste0(output_prefix, "_registered_no_reads.csv"), row.names = FALSE)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
cat(sprintf("\nupload_dir: %s  (use this as -d for bulk_webincli.py)\n", upload_dir_abs))
if (n_abs > 0) {
  ex <- which(grepl("^/", sheet$.r1_in))[1]
  cat(sprintf("Absolute paths converted to relative to upload_dir: %d\n", n_abs))
  if (!is.na(ex)) cat(sprintf("  e.g. %s\n    -> %s\n", sheet$.r1_in[ex], sheet$.r1[ex]))
}

n_multi_sets <- sum(dup_report$read_sets > 1)
if (nrow(dup_report) > 0)
  cat(sprintf("\nWarning: %d samples have more than one samplesheet row - see %s_duplicate_rows.csv\n  %d with more than one read set (%d experiments named %s<alias>_1, _2, ...)\n  %d with identical duplicate rows (left out - see %s_file_problems.csv)\n",
              nrow(dup_report), output_prefix, n_multi_sets,
              sum(dup_report$read_sets[dup_report$read_sets > 1]), experiment_prefix,
              sum(dup_report$identical_duplicate_rows > 0), output_prefix))

cat("\nSummary\n")
cat(sprintf("  Written to %s.tsv: %d experiments (%d samples)\n", output_prefix,
            nrow(submission), length(unique(ok$.alias))))
cat(sprintf("  Not registered yet (%s_pending.csv): %d read sets\n", output_prefix, nrow(pending)))
cat(sprintf("  Left out - FASTQ/duplicate-row problems (%s_file_problems.csv): %d rows\n",
            output_prefix, nrow(problems)))
cat(sprintf("  Registered but no reads in samplesheet (%s_registered_no_reads.csv): %d\n",
            output_prefix, length(no_reads)))
if (nrow(problems) > 0) {
  cat(sprintf("\nFirst problems (first 10 - full list in %s_file_problems.csv):\n", output_prefix))
  print(utils::head(problems, 10), row.names = FALSE, right = FALSE)
}
