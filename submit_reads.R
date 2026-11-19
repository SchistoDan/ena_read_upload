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
##   samples_report  CSV downloaded from Webin (Samples > Samples Report),
##                   with the sample accession ('id') and alias ('alias')
##
## Outputs (prefix set by output_prefix)
##   <prefix>.tsv                     submission spreadsheet for bulk_webincli.py
##   <prefix>_pending.csv             samplesheet rows not in the Samples Report
##                                    (not registered yet) - submit later
##   <prefix>_file_problems.csv       samples left out because of a FASTQ problem
##   <prefix>_registered_no_reads.csv samples in the Samples Report with no
##                                    samplesheet row (for information)
##
## Run with:  Rscript submit_reads.R   (after editing the settings below)
## Base R only - no packages needed.
##############################################################################

# ---------------------------------------------------------------------------
# Settings - edit these
# ---------------------------------------------------------------------------
samplesheet_file    <- "samplesheet.csv"
samples_report_file <- "ena-registered-samples.csv"
output_prefix       <- "sequence_submission"

# Parent directory of the FASTQ files: the same directory given to
# bulk_webincli.py with -d. Paths in the samplesheet are relative to it
# (absolute paths are used as they are).
upload_dir <- "."

study_accession       <- "PRJEBXXXXX"
experiment_prefix     <- "BGE_"          # experiment_name = prefix + sample alias
sequencing_platform   <- "ELEMENT"       # ENA permitted values, e.g. ILLUMINA
sequencing_instrument <- "Element AVITI" # e.g. "Illumina NovaSeq 6000"
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

# Check one FASTQ file; returns "" if fine, otherwise the problem
check_fastq <- function(path) {
  if (path == "") return("no path given")
  full <- if (grepl("^/", path)) path else file.path(upload_dir, path)
  if (!file.exists(full)) return(paste("file not found:", full))
  if (dir.exists(full)) return(paste("path is a directory:", full))
  if (file.size(full) == 0) return(paste("file is empty:", full))
  if (!grepl("\\.gz$", path)) return(paste("not a .gz file name:", path))
  con <- file(full, "rb"); magic <- readBin(con, "raw", n = 2); close(con)
  if (length(magic) < 2 || magic[1] != as.raw(0x1f) || magic[2] != as.raw(0x8b))
    return(paste("not gzip-compressed:", full))
  ""
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

sheet$.alias <- clean(sheet[[alias_col]])
sheet$.r1    <- clean(sheet[[r1_col]])
sheet$.r2    <- clean(sheet[[r2_col]])
sheet$.desc  <- if (is.na(desc_col)) "" else clean(sheet[[desc_col]])
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
# Duplicates in the samplesheet
# ---------------------------------------------------------------------------
problems <- data.frame(sample_alias = character(), problem = character(),
                       stringsAsFactors = FALSE)
dup <- duplicated(sheet$.alias) | duplicated(sheet$.alias, fromLast = TRUE)
if (any(dup)) {
  problems <- rbind(problems, data.frame(sample_alias = unique(sheet$.alias[dup]),
                                         problem = "sample_alias appears more than once in the samplesheet"))
  sheet <- sheet[!dup, ]
}

# ---------------------------------------------------------------------------
# Registered vs pending
# ---------------------------------------------------------------------------
sheet$.accession <- unname(accession_by_alias[sheet$.alias])
registered <- sheet[!is.na(sheet$.accession), ]
pending    <- sheet[is.na(sheet$.accession), ]

# ---------------------------------------------------------------------------
# FASTQ checks (registered samples only)
# ---------------------------------------------------------------------------
keep <- rep(TRUE, nrow(registered))
for (i in seq_len(nrow(registered))) {
  issues <- c(check_fastq(registered$.r1[i]), check_fastq(registered$.r2[i]))
  if (registered$.r1[i] != "" && registered$.r1[i] == registered$.r2[i])
    issues <- c(issues, "uploaded file 1 and uploaded file 2 are the same file")
  issues <- issues[issues != ""]
  if (length(issues) > 0) {
    keep[i] <- FALSE
    problems <- rbind(problems, data.frame(sample_alias = registered$.alias[i],
                                           problem = paste(issues, collapse = "; ")))
  }
}
ok <- registered[keep, ]

# Each FASTQ should only be used once across the submission
used <- c(ok$.r1, ok$.r2)
reused <- unique(used[duplicated(used)])
if (length(reused) > 0) {
  bad <- ok$.r1 %in% reused | ok$.r2 %in% reused
  problems <- rbind(problems, data.frame(sample_alias = ok$.alias[bad],
                                         problem = "FASTQ file used by more than one sample"))
  ok <- ok[!bad, ]
}

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
submission <- data.frame(
  study_accession       = rep(study_accession, nrow(ok)),
  sample_accession      = ok$.accession,
  experiment_name       = paste0(experiment_prefix, ok$.alias),
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

pending_out <- data.frame(sample_alias = pending$.alias,
                          "uploaded file 1" = pending$.r1, "uploaded file 2" = pending$.r2,
                          check.names = FALSE, stringsAsFactors = FALSE)
write.csv(pending_out, paste0(output_prefix, "_pending.csv"), row.names = FALSE)
write.csv(problems, paste0(output_prefix, "_file_problems.csv"), row.names = FALSE)

no_reads <- setdiff(names(accession_by_alias), all_sheet_aliases)
write.csv(data.frame(sample_alias = no_reads,
                     sample_accession = unname(accession_by_alias[no_reads])),
          paste0(output_prefix, "_registered_no_reads.csv"), row.names = FALSE)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
n_abs <- sum(grepl("^/", c(submission[["uploaded file 1"]], submission[["uploaded file 2"]])))
if (n_abs > 0)
  cat(sprintf("\nNote: %d FASTQ paths are absolute. bulk_webincli.py expects paths relative to -d (upload_dir).\n", n_abs))

cat("\nSummary\n")
cat(sprintf("  Written to %s.tsv: %d samples\n", output_prefix, nrow(submission)))
cat(sprintf("  Not registered yet (%s_pending.csv): %d\n", output_prefix, nrow(pending)))
cat(sprintf("  Left out - FASTQ/samplesheet problems (%s_file_problems.csv): %d\n",
            output_prefix, nrow(problems)))
cat(sprintf("  Registered but no reads in samplesheet (%s_registered_no_reads.csv): %d\n",
            output_prefix, length(no_reads)))
if (nrow(problems) > 0) {
  cat("\nFirst problems:\n")
  print(utils::head(problems, 10), row.names = FALSE)
}
