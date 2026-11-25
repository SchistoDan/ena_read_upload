# ENA SUBMISSIONS SOP
**Date:** 2026-11-25

**Author:** Maria Kamouyiaros & Dan Parsons @NHMUK


## Background
The following steps were used to prepare all files needed for submission of genomic skim data generated in UKBOL_Accelerated to the [European Nucleotide Archive (ENA)](https://www.ebi.ac.uk/ena/browser/home), with the assumption that work is performed from a HPC or unix operating system with full access to all UKBOL pipeline outputs and data. 
Each is desgined based on instructions and requirements set by ENA as under their [ENA metadata model](https://ena-docs.readthedocs.io/en/latest/submit/general-guide/metadata.html). 

<p align="center">
  <img src="https://github.com/museomics/ukbol_submissions/blob/main/img/ENA_metadata_model.png" width="600" height="500"
    alt="ENA metadata model flowchart">
  <figcaption>Image taken from ENA's general guide. </figcaption>
</p


#

## Requirements

**1. A valid ENA Webin login**
An account can be registered [here](https://www.ebi.ac.uk/ena/submit/webin/login)

**2. A registered study and study accession number**
This can be found on the webin login page: 
<p align="center">
  <img src="https://github.com/museomics/ukbol_submissions/blob/main/img/ENA_study_registration.png" width="600" height="500"
    alt="Webin register study">
</p
With a guide on how to register available [here](https://ena-docs.readthedocs.io/en/latest/submit/study.html).

**3. Spreadsheet of sample metadata**
- Format: CSV UTF-8
- Must contain values for (at minimum) all mandatory fields listed in the [Tree of Life Checklist (ERC000053)](https://www.ebi.ac.uk/ena/browser/view/ERC000053)

| Tree of Life value| Description|
|---|---|
| tax_id | A valid taxonomic ID - In UKBOL this is in 2 separate spreadsheets where taxIDs were searched externally (see `Sample Registration` below) and 476 new IDs were registered|
| scientific_name| Valid taxonomic name to min. species level (if genus information only then in the format of "Genus sp.". Note: unidentified species of genera have unique tax IDs that are different from the genus tax ID)| 
|sample_alias|A unique alias for each sample - for UKBOL this had the format of UKXXX-XX|
|sample_title|Voucher and alias information - for UKBOL this had the format of: NHM voucher: NHMUKXXXXXXXX; Sample ID: UKXXX-XXX|
|sample_description|Recorded taxonomic name associated with specimen|
|organism part|The part of the organism used to extract DNA (e.g., whole/ 1 leg/ 2 legs)|
|lifestage| Lifestage of organism|
|project name| The registered study ID |
|collected_by| Recorded sample collectors name|
|collection date| Recorded sample collection date in the format YEAR-MONTH-DAY|
|geographic location (latitude)| Recorded latitude in decimal degrees (max. 8 dp)|
|geographic location (longitude)|Recorded longitude in decimal degrees (max. 8 dp)|
|geographic location (region and locality)| Recorded sampling locality| 
|geographic location (country and/or sea)| Recorded sampling country|
|habitat| Recorded habitat information (in most cases not recorded)|
|sex| Recorded sex of organism (in most cases not recorded)|
|collecting institution| Collecting institution name (Natural History Museum, London)|
|specimen_voucher| Museum specimen voucher number|

[Where data is missing record "missing: third party data" unless specified otherwise under INSDC Missing Value Reporting Terms](https://ena-docs.readthedocs.io/en/latest/submit/samples/missing-values.html)

**4. An install of R (v >4.3.0)**
- This can be on any operating system you like
- `02_submit_reads.R` uses base R only (no packages needed)

**5. An install of Python (v >3.11)**
- Many scripts (e.g., ENA bulk webin-cli and assess_mitogenomes.py) require python to run (run with Python v3.12.8)

**6. An install of ENA bulk webin-cli**
- This is available for install with associated information [here](https://github.com/enasequence/ena-bulk-webincli/tree/master), together with a [Webin-CLI](https://github.com/enasequence/webin-cli/releases) `.jar` (tested with 11.0.0) and Java
- With Webin-CLI 11, apply [bulk_webincli.patch](bulk_webincli.patch) to `bulk_webincli.py` (see `Sequencing read submission`, Step 5)

**7. Access to skim2mito outputs**
- This is generated as part of the UKBOL Accelerated pipeline, where [skim2mito](https://github.com/o-william-white/skim2mito) was run on all samples, with outputs sent to a single parent directory called `skim2mito_outputs`

## Building the checklist from taxid-minting outputs (`01_tol_checklist_formatter.py`)

For batches processed with the [taxid-minting workflow](https://github.com/museomics/taxid-minting-process), `01_tol_checklist_formatter.py` builds the Tree of Life checklist (ERC000053) automatically. It joins the original specimen metadata to each sample's ENA taxid. It writes one row per sample that has a taxid, and lists every other sample in the batch, with the reason, in a separate file.

**Requirements:** Python 3.8+ with `pandas`, `openpyxl` and `requests` (`pip install pandas openpyxl requests`).

**Run:**
```bash
python 01_tol_checklist_formatter.py \
    -m sample_metadata.csv \
    --species 00_filter_taxonomy_out_species.csv \
    --non-species 00_filter_taxonomy_out_non_species.csv \
    --ena1 01_ena_check_species-ena_matches.csv \
    --ena2 04_ena_post_ver-ena_matches.csv \
    --verified 03_gbif_processor_manually_verify-complete.xlsx \
    --request-form combined_request_form.tsv \
    --ena1-status 01_ena_check_species.csv \
    --ena2-status 04_ena_post_ver.csv \
    -p BGE \
    -o ./sample_registration/BGE_batch1 \
    --out-format xml --batch 4 \
    --query-ena
```

| Argument | Description |
|---|---|
| `-m` / `--metadata` | Original sample metadata (CSV/TSV/XLSX). It may also contain samples outside this batch, which are ignored |
| `--id-col` | Metadata column holding the Process ID (default `Process ID`). This becomes `sample_alias` |
| `--species` | `00_filter_taxonomy` species-level output. Defines the batch (repeatable). If an ID appears in more than one batch file (e.g. a sample re-run through 00), a species-level entry wins over a genus-level one, and otherwise the file given later wins |
| `--non-species` | `00_filter_taxonomy` genus-level and above output (optional, repeatable) |
| `--ena1` | `01_ena_taxid_check.py` `*-ena_matches.csv` (repeatable) |
| `--ena2` | `04_post_ver_ena_check.py` `*-ena_matches.csv` (optional, repeatable) |
| `--verified` | Manually verified sheet(s) used as 04 input (optional, repeatable). Maps each original name to its `confirmed_taxonomy` |
| `--query-ena` | Look up samples still without a taxid on ENA `suggest-for-submission` (v2). This picks up taxids minted since the request forms were sent |
| `--request-form` | Taxid request TSV(s) submitted to ENA (optional, repeatable). Used only to explain why samples have no taxid yet |
| `--ena1-status` | Any 01 output with `ID` and `ena_status_1`, e.g. the combined output (optional, repeatable). Used to explain missing taxids |
| `--ena2-status` | Any 04 output with `ID` and `ena_status_2`, e.g. the combined output (optional, repeatable). Used to explain missing taxids |
| `--out-format` | `tsv` (default): Webin spreadsheet upload. `xml`: ENA sample XML plus submission XML for programmatic submission |
| `--batch` | Split the checklist output into N files of near-equal size (default 1). Use it when Webin rejects a large file |
| `--checklist-version` | ERC000053 version written on the TSV's first line (default `1.10`; check the template downloaded from Webin) |
| `-p` / `--project` | Value for `project name` (e.g. `BGE`) |
| `-o` / `--output` | Output base path |

**Where each sample's taxid comes from** (first match wins; disagreements are logged):
1. The 01 ENA match for the sample's ID.
2. The 04 ENA match for the sample's ID.
3. The 04 ENA match for the sample's confirmed name. Verified sheets are usually reduced to one row per species, so the confirmed name's taxid is applied to every specimen of that species.
4. With `--query-ena`: an exact, submittable match on ENA for the name that was sent for minting. That is the confirmed name, the original species name, or `Genus sp. {Process ID}` for genus-level samples. Ambiguous matches are not used.

**Field mapping:**

| Checklist field | Source |
|---|---|
| tax_id, scientific_name, sample_description | ENA taxid and ENA scientific name |
| sample_alias | Process ID |
| sample_title | `Voucher: {specimen_voucher}; Sample ID: {Sample ID}` |
| organism part, collected_by, habitat, sex, specimen_voucher | the metadata column of the same name (`sex` is free text and kept as recorded) |
| lifestage | `lifestage`, mapped to ENA's list (adult, egg, embryo, gametophyte, juvenile, larva, zygote, vegetative structure, vegetative cell, sporophyte, spore-bearing structure, pupa, not provided, not collected, not applicable). Variants are mapped: `Adult`, `a`, `flowering`, `Polyp`, `Medusa` and `Polygastric` → adult; `juvenil`, `Immature`, `Subadult` and `Tritonymph` → juvenile; `Larvae` and `metacercaria` → larva; `Pupae` → pupa; `female` and `male` → adult. Other values become `missing: third party data` and are listed in the log |
| project name | `-p` |
| collection date | `collection_date`, converted to `YYYY-MM-DD` (partial dates kept as `YYYY-MM` / `YYYY`). Unreadable dates, future dates and years before 1700 become `missing: third party data` and are listed in the log |
| geographic location (latitude / longitude) | `latitude` / `longitude`, decimal degrees, max 8 dp, range-checked |
| geographic location (region and locality) | `geographic_location_locality` |
| geographic location (country and/or sea) | `geographic_location`, matched to ENA's country list. Variants are mapped: Turkey → Turkiye (ENA's spelling), North Atlantic Ocean → Atlantic Ocean, United States → USA, Cabo Verde → Cape Verde, Vietnam → Viet Nam, Aland → Finland, French Southern Territories → French Southern and Antarctic Lands. `Unspecified country`, `Unrecoverable` and `Exception - Zoological Park` → `missing: third party data`. Any other value not on the list is kept and listed in the log for correction |
| collecting institution | `collecting_institution` |

Empty, `NaN`, `N/A`, `na` and `not collected` values become `missing: third party data`. The mandatory fields (organism part, lifestage, project name, collected_by, collection date, region and locality, habitat, sex, country and/or sea, collecting institution) are never left blank. If a value, or a whole source column, is missing, the field is filled with `missing: third party data` and the fill is counted in the log. Unreadable dates and unusable coordinates are also written as `missing: third party data` and listed in the log.

**Outputs:**

| File | Contents |
|---|---|
| `*_tol_checklist.tsv` (`--out-format tsv`) | The checklist, ready for ENA Webin sample registration: UTF-8, tab-separated, one row per sample with a taxid. Columns are in the order of the Webin ERC000053 v1.10 template. It already includes the `Checklist	ERC000053:1.10	Tree of Life Checklist` line above the field names (set the version with `--checklist-version` if ENA updates the checklist; check the template downloaded from Webin) and the `#units` line (`DD` under latitude and longitude) below them, so no editing is needed. Open it in a text editor rather than Excel: Excel reformats the dates |
| `*_sample.xml` + `*_submission.xml` (`--out-format xml`) | ENA sample XML (one `SAMPLE` per row: `alias`, `TITLE`, `SAMPLE_NAME` with `TAXON_ID`/`SCIENTIFIC_NAME`, `DESCRIPTION`, one `SAMPLE_ATTRIBUTE` per other field, `ENA-CHECKLIST` = `ERC000053`; latitude/longitude always carry `<UNITS>DD</UNITS>`) and the submission XML with the `ADD` action |
| `*_batch{i}of{N}` | With `--batch N`, the TSV or sample XML is split into N files. Each TSV batch repeats the three header lines; each XML batch is a complete `SAMPLE_SET` submitted with the same `*_submission.xml` |
| `*_not_included.csv` | Batch samples not included, with their Sample ID, the reason (see below), the name used for the ENA lookup, the matched request-form name and the raw 01/04 statuses |
| `*_tol_checklist.log` | Taxid sources, conflicts, missing-value counts, lifestage and country changes, date and coordinate problems, and a reconciliation (`included + not included = batch total`) |


**Why a sample is not included** (`reason` column; the first that applies):

| Reason | Meaning | What to do |
|---|---|---|
| `requested (non-species form)` / `requested (species form)` | The name sent for minting is on a `--request-form` file | Wait for ENA, then re-run with `--query-ena` |
| `verification: confirmed_taxonomy empty` | 04 status `MAN_VER_NAME_EMPTY`, or the verified sheet has no confirmed name | Complete manual verification and re-run 04 |
| `possible homonym (04)` / `possible homonym (01)` | `MATCH_PHYLUM_UNCHECKED` or `TAXONOMIC_MISMATCH_HOMONYM`, and the name was not requested | Check the taxon manually |
| `ENA error (01/04)` | An `API_ERROR` status in 01 or 04 | Re-run that step |
| `conflicting confirmed names` | The original name maps to more than one confirmed name in the verified sheets | Make the verified sheets agree |
| `not on any request form` | No taxid, and the name is on none of the supplied request forms (shown as `no taxid yet` when no forms are given) | Check whether it was dropped from the forms |
| `Process ID not found in metadata` | The sample has a taxid but no metadata row | Add it to the metadata |

With `--query-ena`, the lookup result is added, e.g. `requested (species form); ENA lookup: not found in ENA`.

**Name trimming (matching only):** when matching samples to the request forms and looking names up on ENA, the script also tries a trimmed name:
- qualifiers are removed: `cf.`, `aff.`, `nr.`, `s.l.`, `s.str.`, `sensu lato`, `agg.`, `complex`, `group`;
- bracketed text is removed, e.g. `(Pennant, 1777)`;
- trailing codes are dropped. For example, `Troglochthonius doratodactylus GP` matches `Troglochthonius doratodactylus`, and `Alvania aff. moerchii` matches `Alvania moerchii`;
- a lower-case subspecies is kept. Names without a proper epithet, e.g. `Eunice sp2`, are not trimmed to a species.

Form names written as `Genus sp. {ID}` are also matched by the ID, even if the genus was changed at verification. The `request_form_name` column shows the form name each sample was matched to. The registered `scientific_name` is always ENA's name for the taxid. The log counts samples per reason. For the `requested` reasons it also shows the number of unique request-form names. Not-included rows are per specimen, while species request forms list each name once, so the two totals are not expected to match.

**Lat/lon:** `geographic location (latitude)` and `(longitude)` are optional in ERC000053. Their format rule accepts decimal degrees (max. 8 dp) or an INSDC missing-value term such as `missing: third party data`. The formatter writes that term for empty or unusable coordinates, so its TSV can be submitted as a single file with no lat/lon split.

**The TSV files are then ready for submission via the ENA Webin**:

<p align="center">
  <img src="https://github.com/museomics/ukbol_submissions/blob/main/img/ENA_sample_registration.png" width="400" height="300"
    alt="ENA Webin sample registration">
</p

Alternatively, you can **Submit the XML programmatically** (check the URLs against [ENA's programmatic submission docs](https://ena-docs.readthedocs.io/en/latest/submit/samples/programmatic.html)). Test on the test server first; it validates everything but does not keep the samples:
```bash
curl -u Webin-XXXXX:PASSWORD -F "SUBMISSION=@BGE_batch1_submission.xml" -F "SAMPLE=@BGE_batch1_sample_batch1of4.xml" "https://wwwdev.ebi.ac.uk/ena/submit/drop-box/submit/"
```
Then use `https://www.ebi.ac.uk/ena/submit/drop-box/submit/` for the real submission. The receipt XML reports `success="true"` with the sample accessions, or lists the error for each failing sample by alias.



## Sequencing read submission 

Paired-end reads are submitted in two steps:

| Script | What it does |
|---|---|
| [02_submit_reads.R](02_submit_reads.R) | Joins a samplesheet of FASTQ paths to the ENA Samples Report, checks every FASTQ file, and writes the submission TSV (one row per experiment, i.e. per read set) |
| [03_ena_bulk_webincli.sh](03_ena_bulk_webincli.sh) | SLURM job that runs the [ena bulk webincli tool](https://github.com/enasequence/ena-bulk-webincli/tree/master) on that TSV. The tool writes a [manifest file](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html) for each row and calls Webin-CLI. It is run **twice**: first with `MODE="validate"`, then, once every row has passed, with `MODE="submit"` |

**Submission TSV fields** (written by `02_submit_reads.R`):

|Value| Description |
|---|---|
|study_accession| Project (study) accession number, e.g. `PRJEBXXXXX`|
|sample_accession| Sample accession from ENA, taken from the Webin Samples Report | 
|experiment_name| A unique experiment name: `experiment_prefix` + sample alias (e.g. `BGE_BSNTN2426-24`). A sample with replicates gets one experiment per replicate: `BGE_<alias>_1`, `BGE_<alias>_2`, … (numbered in samplesheet order)|
|sequencing_platform| Sequencing platform used. [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#platform)|
|sequencing_instrument|Sequencing instrument used. [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#instrument)| 
|library_source| Source molecule, e.g., `GENOMIC` [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#source)| 
|library_selection|Library selection, e.g. `RANDOM` [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#selection)|
|library_strategy|Sequencing strategy, e.g., whole genome sequencing (`WGS`). [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#strategy)|
|library_description| Description of the library: from the samplesheet if given, otherwise `default_library_description` set in the script| 
|uploaded file 1|Gzipped forward (R1) read file, relative to the upload directory (`-d`)|
|uploaded file 2|Gzipped reverse (R2) read file, relative to the upload directory (`-d`)| 

`library_name` is optional for ENA reads and is not included.

### Step 1: Download the Samples Report

Download the registered samples from the Webin portal (Samples > Samples Report) as CSV. It must contain the sample accession (`id`) and the sample alias (`alias`). Download it after **all** sample registrations are complete, so every registered sample is included.

<p align="center">
  <img src="https://github.com/museomics/ukbol_submissions/blob/main/img/ENA_sample_download.png" width="400" height="300"
    alt="ENA Webin Sample metadata download">
</p>

### Step 2: Prepare the samplesheet

A CSV with one row per read set:

| Column | Required | Description |
|---|---|---|
| `sample_alias` | Yes | The sample alias used at registration (Process ID) |
| `uploaded file 1` | Yes | R1 FASTQ (`.fastq.gz`): an absolute path, or a path relative to `upload_dir` |
| `uploaded file 2` | Yes | R2 FASTQ (`.fastq.gz`): an absolute path, or a path relative to `upload_dir` |
| `library_description` | No | Overrides the default library description for that row |

- The samplesheet can include samples that are not registered yet (e.g. still waiting for taxids to be minted). They are not submitted, and are listed in `_file_problems.csv` as `not registered` (see Step 4 and Step 8).
- FASTQs must be decompressed `.fastq.gz` files, not inside a `.tar`/`.tar.gz` archive.
- A sample can have several rows. There are two cases:
  - **Replicate:** the same `sample_alias` with **different** FASTQs, e.g. a sample sequenced more than once. Every replicate is submitted as its own experiment, `BGE_<alias>_1`, `BGE_<alias>_2`, … (numbered in samplesheet order), and is listed in `_replicate_rows.csv`.
  - **Duplicate:** the same `sample_alias` **and** the same `uploaded file 1` and `uploaded file 2`. The first copy is submitted. Each later copy is left out and listed in `_file_problems.csv` as `duplicate row`.

  For example:

  | Row | sample_alias | FASTQs | Result |
  |---|---|---|---|
  | 1 | EBGEP999-25 | YG-4378 … S1314_L006_R1/R2 | submitted as `BGE_EBGEP999-25_1` |
  | 2 | EBGEP999-25 | YG-4379 … S226_L002_R1/R2 | submitted as `BGE_EBGEP999-25_2` (replicate) |
  | 3 | EBGEP999-25 | same as row 2 | left out, in `_file_problems.csv` (duplicate of `BGE_EBGEP999-25_2`) |

### Step 3: Edit the settings in `02_submit_reads.R`

| Setting | Description |
|---|---|
| `samplesheet_file` | The samplesheet from Step 2 |
| `samples_report_file` | The Samples Report from Step 1 |
| `output_prefix` | Prefix for the output files (default `read_submission`) |
| `upload_dir` | The directory you will give to `bulk_webincli.py` with `-d`, i.e. `OUTPUT_DIR` in `03_ena_bulk_webincli.sh` (see below) |
| `study_accession` | Your project accession (`PRJEB...`) |
| `experiment_prefix` | Prefix for `experiment_name`, e.g. `BGE_` |
| `sequencing_platform`, `sequencing_instrument` | e.g. `ILLUMINA` / `Illumina NovaSeq X`, or `ELEMENT` / `Element AVITI` |
| `library_source`, `library_selection`, `library_strategy` | e.g. `GENOMIC` / `RANDOM` / `WGS` for genome skims |
| `default_library_description` | Used when the samplesheet has no `library_description` |

**`upload_dir` and FASTQ paths.**
- `bulk_webincli.py` passes `-d` to Webin-CLI as the input directory, and every FASTQ path in the TSV must be relative to it.
- `bulk_webincli.py` also writes its `manifests/` and `submissions/` folders and its failure file into `-d`. A convenient choice is a `read_upload` folder next to your outputs.
- `02_submit_reads.R` rewrites every absolute path in the samplesheet relative to `upload_dir`, adding `../` where needed. For example, with `upload_dir` set to `…/non_BSNHM_skims-1/read_upload`, `/mnt/shared/projects/nhm/museomix/BGE/seq_data/DataDelivery_…/…_R1_001.fastq.gz` becomes `../../../../../seq_data/DataDelivery_…/…_R1_001.fastq.gz`.
- The script resolves symlinks in folder names, so the `../` part may be shorter than you expect.
- File names are kept as written, and paths that are already relative are left unchanged.
- The samplesheet itself is not modified, and `_file_problems.csv` keeps the paths as written.

> **`-d` must be exactly `upload_dir`.** The `../` paths only resolve from that directory. If `-d` is a different folder, even a sub-folder such as `read_upload/validated`, every row fails with `ERROR: Could not read data file`.

### Step 4: Run `02_submit_reads.R`

```
Rscript 02_submit_reads.R
```

The script:
- rewrites absolute FASTQ paths relative to `upload_dir`;
- numbers replicates (`_1`, `_2`, …), and leaves out the later copies of duplicate rows;
- joins the samplesheet to the Samples Report by sample alias. Rows whose alias is not in the report are left out as `not registered`, without checking their files;
- checks each read set separately:
  - every FASTQ file exists, is not empty and is gzip-compressed;
  - R1 and R2 are different files;
  - no file is used by two read sets.

  If one read set of a sample fails, that sample's other read sets are still submitted;
- writes the outputs below, and prints:
  - `upload_dir` (the `-d` to use);
  - the number of paths converted, with an example;
  - warnings for replicates and duplicate rows;
  - a summary of the counts;
  - the first 10 FASTQ and duplicate problems.

| Output | Contents |
|---|---|
| `read_submission.tsv` | The spreadsheet for `bulk_webincli.py`: one row per experiment (read set) of registered samples whose FASTQ files passed every check |
| `read_submission_file_problems.csv` | Every samplesheet row left out. Columns: `sample_alias`, `experiment_name`, `uploaded file 1`, `uploaded file 2` (as written in the samplesheet), `problem_type` and `problem` (the reason). The `problem_type` values are listed below |
| `read_submission_replicate_rows.csv` | Samples with replicates: number of samplesheet rows, number of replicates, duplicate rows left out, and the experiment names |
| `read_submission_registered_no_reads.csv` | Registered samples with no row in the samplesheet (for information) |

`problem_type` in `read_submission_file_problems.csv`:

| problem_type | Why | What to do |
|---|---|---|
| `not registered` | The `sample_alias` is not in the `alias` column of the Samples Report: not registered yet (e.g. waiting for a taxid, or a failed registration batch), registered after the report was downloaded, or registered under a different alias. The match ignores leading and trailing spaces, but is otherwise exact and case-sensitive | Register the samples, download a new Samples Report and re-run (Step 8) |
| `FASTQ problem` | Missing, empty or non-gzipped file, R1 = R2, or a file used by two read sets | Fix the file or the samplesheet path and re-run |
| `duplicate row` | Identical to an earlier row; the first copy was submitted | Nothing; remove the extra copy from the samplesheet if you like |

The run's counts add up: rows written + rows in `_file_problems.csv` = samplesheet rows. The TSV usually has more experiments than samples, because each replicate is its own experiment.

Check the summary before continuing. The console shows only the first 10 FASTQ and duplicate problems, so open the CSV for the full list. Experiment numbers are assigned before the file checks, so a read set keeps its name when you re-run after fixing a file.

### Step 5: Set up `03_ena_bulk_webincli.sh`

**Patch `bulk_webincli.py` (once).** The upstream `bulk_webincli.py` looks for an old Webin-CLI success message. With Webin-CLI 11 it therefore logs every run as `VALIDATION FAILED`, including the ones that passed. [bulk_webincli.patch](bulk_webincli.patch) fixes this:
- **Validate:** a run passes on Webin-CLI 11's `Submission(s) validated successfully.`
- **Submit:** a run passes on `The submission has been completed successfully. The following … accession was assigned`. A submission with no accession assigned is marked FAILED.
- **Errors:** any `ERROR:` line marks the run FAILED.
- **Labels and failure files:** submit runs are logged as `SUBMISSION SUCCESSFUL/FAILED` and written to `failed_submission.txt`. Validate runs keep `failed_validation.txt`.
- **Password:** your password is masked (`********`) in the printed commands, so it is no longer written to the job log.

Apply it from the `ena-bulk-webincli` folder, then check it:
```bash
cp bulk_webincli.py bulk_webincli.py.bak
patch bulk_webincli.py < /path/to/ena_read_upload/bulk_webincli.patch
grep -n 'SUCCESS_MESSAGES\|"\*\*\*\*\*\*\*\*"' bulk_webincli.py
```
The `grep` should list the `SUCCESS_MESSAGES` lines and the masking line. Re-apply the patch after updating or reinstalling ena-bulk-webincli.

**Edit the variables at the top of `03_ena_bulk_webincli.sh`:**

| Variable | Description |
|---|---|
| `ENA_BULK_WEBINCLI` | Path to the patched `bulk_webincli.py` |
| `ENA_WEBINCLI_JAR` | Path to the Webin-CLI `.jar` (tested with `webin-cli-11.0.0.jar`) |
| `ENA_ACCOUNT` | Your Webin account, `Webin-XXXXX` |
| `ENA_PASSWORD` | Your Webin password, in **single quotes** so characters such as `!` and `$` are kept as typed. The tool passes the password to Webin-CLI through a shell, so a password containing spaces, `;`, `&` or quotes will not work |
| `INPUT_SHEET` | `read_submission.tsv` from Step 4 (full path) |
| `OUTPUT_DIR` | `-d`: must be the same directory as `upload_dir` in `02_submit_reads.R` (the script prints it) |
| `MODE` | `validate` (Step 6), then `submit` (Step 7) |

**Notes:**
- The job activates the `ena` conda environment with `eval "$(conda shell.bash hook)"`; `conda init` does not work inside a batch job.
- The compute node needs internet access to ENA. Submit mode also uploads every FASTQ by FTP, so check that FTP is allowed, or use the tool's `-a` (Aspera) option if `ascp` is installed.
- Set a generous SLURM time limit. Validation reads every FASTQ in full, and submission also uploads them.
- Run the job from the directory where you want `bulk_webincli.out`/`.err`: `sbatch 03_ena_bulk_webincli.sh`.
- Don't share the job logs: they include your account name and the Webin-CLI output.

### Step 6: Validate (`MODE="validate"`)

Validation generates the manifests and checks the metadata and read files. Nothing is submitted.

1. **One-row test first.** This confirms that Webin-CLI finds the files through the relative paths:
   ```bash
   head -n 2 read_submission.tsv > read_upload/test.tsv
   ```
   Set `INPUT_SHEET` to `test.tsv`, `sbatch 03_ena_bulk_webincli.sh`, and check that the `.out` file in `read_upload/manifests/*-report/` says `VALIDATION SUCCESSFUL`.
2. **Then the full TSV.** Delete the test's `manifests/`, `submissions/` and `failed_validation.txt` first: the failure file is added to on every run, not overwritten. Then set `INPUT_SHEET` back to `read_submission.tsv` and run the job again.
3. **Check the result**, from `read_upload`.

   Number that passed (should equal the number of rows in `read_submission.tsv`):
   ```bash
   grep -rl --include='*.out' "VALIDATION SUCCESSFUL" manifests | wc -l
   ```
   Number that failed (should be 0; also check that `failed_validation.txt` is empty or missing):
   ```bash
   grep -rl --include='*.err' "^ERROR:" manifests | wc -l
   ```
   If any failed, count the error types:
   ```bash
   grep -rh --include='*.err' "^ERROR:" manifests | sed -E 's/"[^"]*"/"…"/g; s/\[manifest file.*//' | sort | uniq -c | sort -rn
   ```

The logback `INFO`/`WARN` lines at the start of every Webin-CLI log are start-up messages and can be ignored. The shared `submissions/webin-cli.report` is overwritten by each row, so it only shows the last one. Use the per-row reports in `manifests/*-report/`.

**Only continue to Step 7 when every row has passed.** Fix any failures (usually in the samplesheet, then re-run Step 4) and validate again.

### Step 7: Submit (`MODE="submit"`)

Submission uploads the FASTQs and registers the experiments and runs. It can't be undone from your side; removing runs needs the ENA helpdesk.

1. **Clear the validate outputs.** Delete `manifests/`, `submissions/` and `failed_validation.txt` in `read_upload`.
2. **One-row submit first.** Use `INPUT_SHEET` = `test.tsv` and `MODE="submit"`. Check that its `.out` file says `SUBMISSION SUCCESSFUL` and shows the assigned accession, and that the experiment and run appear in the Webin portal (Experiments, Runs). This also confirms the node can upload by FTP.
3. **Then the full TSV.** Remove that row from `read_submission.tsv` first, because it has already been submitted. Then run the job with `MODE="submit"`.
4. **Check the result**, from `read_upload`.

   Both counts should equal the number of rows submitted:
   ```bash
   grep -rl --include='*.out' "SUBMISSION SUCCESSFUL" manifests | wc -l
   ```
   ```bash
   grep -rh --include='*.out' "accession was assigned" manifests | wc -l
   ```
   Any failures are in `failed_submission.txt`.

- **If the job stops partway:** you can re-run with a TSV of only the failed or unsubmitted rows. ENA identifies experiments and runs by name within your account, so a row that already went through is reported as an error rather than submitted twice. Check the wording in `failed_submission.txt`.
- **When the runs become public:** they follow the release date of the study. If the study is already public, the reads become public once ENA has processed them.
- **Keep the logs:** keep `manifests/*-report/*.out` (the accessions) and the receipts in `submissions/`.

### Step 8: Later submissions (samples registered later)

Rows with `problem_type` = `not registered` are not lost. Once those samples have taxids and are registered (via the taxid-minting workflow and `01_tol_checklist_formatter.py`), submit their reads the same way:

1. Filter them out of the problems file, which can be used directly as the next samplesheet (the extra columns are ignored). Copy it before re-running 02, because a re-run with the same `output_prefix` overwrites `read_submission_file_problems.csv`:
   ```bash
   awk -F'","' 'NR==1 || $5=="not registered"' read_submission_file_problems.csv > not_registered_samplesheet.csv
   ```
   To split by project prefix, e.g. samples for a separate BSNHM submission:
   ```bash
   awk -F'","' 'NR==1 || ($5=="not registered" && $1 ~ /^"BSNHM/)' read_submission_file_problems.csv > bsnhm_samplesheet.csv
   ```
2. Download a new Samples Report after the registrations.
3. Run Steps 3–7 again with these files. Use a new `output_prefix` and a new `upload_dir`/`OUTPUT_DIR`, so the earlier outputs and logs are kept.


## Mitogenome assembly submissions

**Mitogenome successes**

Mitogenome success and submission strategy was assessed by contiguity, length and circularity of final scaffold:

|Category|Submission Type|Description|
|---|---|---|
|Complete mtDNA chromosome| [Chromosome-level assembly](https://ena-docs.readthedocs.io/en/latest/submit/assembly/genome.html) |considered complete if circularised by getOrganelle in [the skim2mito run used to generate the data](https://github.com/o-william-white/skim2mito)|
|Partial mtDNA chromosome | [Chromosome-level assembly](https://ena-docs.readthedocs.io/en/latest/submit/assembly/genome.html)| A single, non-circularised scaffold of minimum length of 5kbp|
|mtDNA assembly| [Contig-level assembly](https://ena-docs.readthedocs.io/en/latest/submit/assembly/genome.html)| Multi-contig assembly, where a minimum of 5 protein-coding genes are present per contig|

> All submissions are taxonomically validated to ensure no contamination
> Any assemblies with gene duplications are removed

To assess this, the [assess_mitogenomes.R](https://github.com/museomics/ukbol_submissions/blob/main/assess_mitogenomes.R) tool. This is a script that contains a function that requires a single argument - the parent directory where all skim2ribo outputs are found. This was run **twice**, once for all batches and once for any repeat sequencing. This can be run by sourcing the script to load the function and then running it with the right filepath: 

```
source(assess_mitogenomes.R)
assess_mitogenomes("./skim2mito_summaries")
assess_mitogenomes("./skim2mito_repeatseq")
```

This function outputs:
1. A csv of all multi-contig assemblies that are eligible for submission
2. A csv of all partial mitochondrial genome assemblies that are eligible for submission
3. A csv of all complete mitochondrial genome assemblies that are eligible for submission
4. A summary of the total number of each type of assembly
5. A text file of valid contigs for each multi-contig sample

The script [parse_contig_assemblies_fun.sh](https://github.com/museomics/ukbol_submissions/blob/main/parse_contig_assemblies_fun.sh) is then run on the output text files to filter out any contigs that are less than 5kbp, have been flagged as contaminant or contain multiple gene copies and to output final FASTA and matching BED (annotation) files. The shell script is a function and can be run as follows:

```
chmod +x parse_contig_assemblies_fun.sh
./parse_contig_assemblies_fun.sh . ./parsed_files
```



**Mitogenome submissions**

To submit mitogenomes the following is required: 
1. Manifest metadata
2. A GZIP compressed FASTA file
3. A TSV of filepaths associated with each sample accession


To get the filepaths for every skim2mito generated assembly run the following: 

```
ls skim2mito_output/*/assembled_sequence/*.fasta.gz | awk -F'/' '{name=$NF; sub(/\.fasta$/, "", name); print $0 "\t" name}' > fasta_files_with_basenames.tsv
```

To link the manifest metadata required, the filepaths and associated sample accessions, the R script [assembly_submissions.R]() was run as follows: 

```

```

Final assembly manifests were then submitted to ENA using a [modified version of the bulk_webincli.py tool](https://github.com/Kamouyiaraki/ena-bulk-webincli_primary_assembly) using the following: 

```
python /path/to/ena-bulk-webincli/bulk_webincli_primary_assembly.py -u Webin-XXXXX -p XXXXXX -g reads -s assembly_submission.tsv -m validate -d UKBOL_accelerated --webinCliPath /path/to/ena-bulk-webincli/webin-cli-9.0.1.jar
python /path/to/ena-bulk-webincli/bulk_webincli_primary_assembly.py -u Webin-XXXXX -p XXXXXX -g reads -s assembly_submission.tsv -m submit -d UKBOL_accelerated --webinCliPath /path/to/ena-bulk-webincli/webin-cli-9.0.1.jar
```
