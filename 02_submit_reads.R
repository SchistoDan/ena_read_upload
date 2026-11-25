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
##                   A sample may have several rows (replicates).
##   samples_report  CSV downloaded from Webin (Samples > Samples Report),
##                   with the sample accession ('id') and alias ('alias')
##
## FASTQ paths
##   bulk_webincli.py passes its -d directory to Webin-CLI as -inputDir, and
##   the paths in the TSV must be relative to it. Absolute paths in the
##   samplesheet are rewritten relative to upload_dir (using ../ where
##   needed), so set upload_dir to the directory you will give to -d.
##
## Replicates and duplicates
##   Replicate: same sample alias, different FASTQs. Every replicate is
##   submitted as its own experiment: BGE_<alias>_1, BGE_<alias>_2, ...
##   (numbered in samplesheet order). Samples with one read set keep
##   BGE_<alias>.
##   Duplicate: same sample alias AND the same two FASTQs. The first copy is
##   submitted; each later copy is left out and reported as a problem.
##
## Outputs (prefix set by output_prefix)
##   <prefix>.tsv                     submission spreadsheet for bulk_webincli.py
##   <prefix>_file_problems.csv       samplesheet rows left out, with the reason:
##                                    not registered (alias not in the Samples
##                                    Report), FASTQ problem, or duplicate row
##   <prefix>_replicate_rows.csv      samples with replicates, and the
##                                    experiment names they get
##   <prefix>_registered_no_reads.csv samples in the Samples Report with no
##                                    samplesheet row (for information)
##
## Run with:  Rscript submit_reads.R   (after editing the settings below)
## Base R only - no packages needed.
##############################################################################
# ---------------------------------------------------------------------------
# Settings - edit these
# ---------------------------------------------------------------------------
samplesheet_file    <- "/home/dparsons/projects/nhm/museomix/BGE/ena_submission/ena-read-upload/ena_read_upload/non_BSNHM_skims-1/read_upload/samplesheets/combined_samplesheet.csv"
samples_report_file <- "/home/dparsons/projects/nhm/museomix/BGE/ena_submission/ena-read-upload/ena_read_upload/non_BSNHM_skims-1/sample_reg/nonBSNHM_BGE_sample_reg-2026-11-19.csv"
output_prefix       <- "read_submission"

# Parent directory of the FASTQ files: the same directory given to
# bulk_webincli.py with -d. Paths in the samplesheet are relative to it
# (absolute paths are used as they are).
upload_dir <- "/home/dparsons/projects/nhm/museomix/BGE/ena_submission/ena-read-upload/ena_read_upload/non_BSNHM_skims-1/read_upload"

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

dup_later <- duplicated(sheet$.key)   # 2nd, 3rd ... copy of an identical row

problems <- data.frame(sample_alias = character(), experiment_name = character(),
                       "uploaded file 1" = character(), "uploaded file 2" = character(),
                       problem_type = character(), problem = character(),
                       check.names = FALSE, stringsAsFactors = FALSE)
add_problem <- function(problems, rows, type, problem) {
  if (nrow(rows) == 0) return(problems)
  rbind(problems, data.frame(sample_alias = rows$.alias, experiment_name = rows$.exp,
                             "uploaded file 1" = rows$.r1_in, "uploaded file 2" = rows$.r2_in,
                             problem_type = type, problem = problem,
                             check.names = FALSE, stringsAsFactors = FALSE))
}

if (any(dup_later))
  problems <- add_problem(problems, sheet[dup_later, ], "duplicate row",
    sprintf("identical duplicate of an earlier row (same sample_alias, uploaded file 1 and uploaded file 2) - first copy kept as %s",
            sheet$.exp[dup_later]))

replicated <- names(n_sets)[n_sets > 1]
rep_report <- data.frame(
  sample_alias            = replicated,
  samplesheet_rows        = as.vector(n_rows[replicated]),
  replicates              = as.vector(n_sets[replicated]),
  duplicate_rows_left_out = vapply(replicated, function(a) sum(dup_later[sheet$.alias == a]), integer(1)),
  experiment_names        = vapply(replicated, function(a) paste(unique(sheet$.exp[sheet$.alias == a]), collapse = ";"),
                                   character(1)),
  stringsAsFactors = FALSE, row.names = NULL)

sheet <- sheet[!dup_later, ]

# ---------------------------------------------------------------------------
# Registered vs not registered
# ---------------------------------------------------------------------------
sheet$.accession <- unname(accession_by_alias[sheet$.alias])
registered <- sheet[!is.na(sheet$.accession), ]
problems <- add_problem(problems, sheet[is.na(sheet$.accession), ], "not registered",
  "sample_alias not in the Samples Report - not registered yet, registered after the report was downloaded, or registered under a different alias; re-run with a new Samples Report once registered")

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
    problems <- add_problem(problems, registered[i, ], "FASTQ problem", paste(issues, collapse = "; "))
  }
}
ok <- registered[keep, ]

# Each FASTQ should only be used once across the submission
used <- c(ok$.r1, ok$.r2)
reused <- unique(used[duplicated(used)])
if (length(reused) > 0) {
  bad <- ok$.r1 %in% reused | ok$.r2 %in% reused
  problems <- add_problem(problems, ok[bad, ], "FASTQ problem", "FASTQ file used by more than one read set")
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

write.csv(problems, paste0(output_prefix, "_file_problems.csv"), row.names = FALSE)
write.csv(rep_report, paste0(output_prefix, "_replicate_rows.csv"), row.names = FALSE)

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

n_type <- function(x) sum(problems$problem_type == x)
if (nrow(rep_report) > 0)
  cat(sprintf("\nWarning: %d samples have replicates (%d experiments named %s<alias>_1, _2, ...) - see %s_replicate_rows.csv\n",
              nrow(rep_report), sum(rep_report$replicates), experiment_prefix, output_prefix))
if (sum(dup_later) > 0)
  cat(sprintf("Warning: %d exact duplicate rows left out (first copy kept) - see %s_file_problems.csv\n",
              sum(dup_later), output_prefix))

cat("\nSummary\n")
cat(sprintf("  Written to %s.tsv: %d experiments (%d samples)\n", output_prefix,
            nrow(submission), length(unique(ok$.alias))))
cat(sprintf("  Left out (%s_file_problems.csv): %d rows - %d not registered, %d FASTQ problems, %d duplicate rows\n",
            output_prefix, nrow(problems), n_type("not registered"), n_type("FASTQ problem"),
            n_type("duplicate row")))
cat(sprintf("  Registered but no reads in samplesheet (%s_registered_no_reads.csv): %d\n",
            output_prefix, length(no_reads)))
shown <- problems[problems$problem_type != "not registered", c("sample_alias", "experiment_name", "problem")]
if (nrow(shown) > 0) {
  cat(sprintf("\nFirst FASTQ/duplicate problems (first 10 - full list in %s_file_problems.csv):\n", output_prefix))
  print(utils::head(shown, 10), row.names = FALSE, right = FALSE)
}
