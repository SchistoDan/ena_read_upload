#!/bin/bash
#SBATCH --job-name=bulk_webincli
#SBATCH --partition=long
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --error=%x.err
#SBATCH --output=%x.out


# Activate conda env ('conda init' does not work inside a batch job)
eval "$(conda shell.bash hook)"
conda activate ena


# Arg definitions
	#-s INPUT_SPREADSHEET can be tab-separated .txt, .csv, .xlsx/.xls or .tsv
	#-pc = parallel cores (between 1 and 10).
	#-m = submit/validate
	#-t = ENA test services
	#-g = genetic context (reads, sequence, genome, transcriptome, taxrefset)


# Paths and variables
ENA_BULK_WEBINCLI="/path/to/ena-bulk-webincli/bulk_webincli.py"   # patched with bulk_webincli.patch
ENA_WEBINCLI_JAR="/path/to/webin-cli/webin-cli-X.X.X.jar"

ENA_ACCOUNT="Webin-XXXXX"
ENA_PASSWORD='XXXXXXX'

INPUT_SHEET="/path/to/read_manifest.tsv"   # TSV written by 02_submit_reads.R
OUTPUT_DIR="/path/to/read_upload/"           # must be upload_dir in 02_submit_reads.R

MODE="validate"   # validate first; change to "submit" only when every row has passed


# Run
python "$ENA_BULK_WEBINCLI" \
	-u "$ENA_ACCOUNT" -p "$ENA_PASSWORD" \
	-g reads -s "$INPUT_SHEET" \
	-m "$MODE" -pc 8 -d "$OUTPUT_DIR" \
	--webinCliPath "$ENA_WEBINCLI_JAR"
