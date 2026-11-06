# ENA SUBMISSIONS SOP FOR UKBOL ACCELERATED

[![DOI](https://zenodo.org/badge/1186149562.svg)](https://doi.org/10.5281/zenodo.19132437)


<p align="center">
  <img src="https://github.com/museomics/ukbol_submissions/blob/main/img/UKBOL%20dragonfly.png" width="200" height="200"
    alt="UKBOL Accelerated logo">
</p>

**Date:** 2026-03-19

**Author:** Maria Kamouyiaros@NHMUK

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
- Packages: dplyr and plyr

**5. An install of Python (v >3.11)**
- Many scripts (e.g., ENA bulk webin-cli and assess_mitogenomes.py) require python to run (run with Python v3.12.8)

**6. An install of ENA bulk webin-cli**
- This is available for install with associated information [here](https://github.com/enasequence/ena-bulk-webincli/tree/master)

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
    --query-ena
```

| Argument | Description |
|---|---|
| `-m` / `--metadata` | Original sample metadata (CSV/TSV/XLSX). It may also contain samples outside this batch, which are ignored |
| `--id-col` | Metadata column holding the Process ID (default `Process ID`). This becomes `sample_alias` |
| `--species` | `00_filter_taxonomy` species-level output. Defines the batch (repeatable) |
| `--non-species` | `00_filter_taxonomy` genus-level and above output (optional, repeatable) |
| `--ena1` | `01_ena_taxid_check.py` `*-ena_matches.csv` (repeatable) |
| `--ena2` | `04_post_ver_ena_check.py` `*-ena_matches.csv` (optional, repeatable) |
| `--verified` | Manually verified sheet(s) used as 04 input (optional, repeatable). Maps each original name to its `confirmed_taxonomy` |
| `--query-ena` | Look up samples still without a taxid on ENA `suggest-for-submission` (v2). This picks up taxids minted since the request forms were sent |
| `--request-form` | Taxid request TSV(s) submitted to ENA (optional, repeatable). Used only to explain why samples have no taxid yet |
| `--ena1-status` | Any 01 output with `ID` and `ena_status_1`, e.g. the combined output (optional, repeatable). Used to explain missing taxids |
| `--ena2-status` | Any 04 output with `ID` and `ena_status_2`, e.g. the combined output (optional, repeatable). Used to explain missing taxids |
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
| organism part, lifestage, collected_by, habitat, sex, specimen_voucher | the metadata column of the same name |
| project name | `-p` |
| collection date | `collection_date`, converted to `YYYY-MM-DD` (partial dates kept as `YYYY-MM` / `YYYY`) |
| geographic location (latitude / longitude) | `latitude` / `longitude`, decimal degrees, max 8 dp, range-checked |
| geographic location (region and locality) | `geographic_location_locality` |
| geographic location (country and/or sea) | `geographic_location` |
| collecting institution | `collecting_institution` |

Empty, `NaN`, `N/A`, `na` and `not collected` values become `missing: third party data`. The mandatory fields (organism part, lifestage, project name, collected_by, collection date, region and locality, habitat, sex, country and/or sea, collecting institution) are never left blank. If a value, or a whole source column, is missing, the field is filled with `missing: third party data` and the fill is counted in the log. Unreadable dates and unusable coordinates are also written as `missing: third party data` and listed in the log.

**Outputs:**

| File | Contents |
|---|---|
| `*_tol_checklist.csv` | The checklist (UTF-8), one row per sample with a taxid |
| `*_not_included.csv` | Batch samples not included, with the reason (see below), the name used for the ENA lookup and the raw 01/04 statuses |
| `*_tol_checklist.log` | Taxid sources, conflicts, missing-value counts, date and coordinate problems, and a reconciliation (`included + not included = batch total`) |

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

With `--query-ena`, the lookup result is added, e.g. `requested (species form); ENA lookup: not found in ENA`. The log counts samples per reason. For the `requested` reasons it also shows the number of unique request-form names. Not-included rows are per specimen, while species request forms list each name once, so the two totals are not expected to match.

**Lat/lon:** `geographic location (latitude)` and `(longitude)` are optional in ERC000053. Their format rule accepts decimal degrees (max. 8 dp) or an INSDC missing-value term such as `missing: third party data`. The formatter writes that term for empty or unusable coordinates, so its CSV can be submitted as a single file with no lat/lon split.


The TSV files are then ready for submission via the ENA Webin.

<p align="center">
  <img src="https://github.com/museomics/ukbol_submissions/blob/main/img/ENA_sample_registration.png" width="400" height="300"
    alt="ENA Webin sample registration">
</p>


## Sequencing read submission 

This information is needed in a single TSV file that can be used to generate a [manifest file](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html). 

|Value| Description |
|---|---|
|study_accession| project accession number|
|sample_accession| Unique sample accession number from ENA - available under Samples > Samples Report | 
|experiment_name| A unique experiment name|
|sequencing_platform| Sequencing platform used. [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#platform)|
|sequencing_instrument|Sequencing instrument used. [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#instrument)| 
|library_name|Identifier for library and sequencing run, e.g., Batch01|
|library_source| Source molecule, e.g., `GENOMIC` [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#source)| 
|library_selection|Library selection, e.g. `RANDOM` [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#selection), 
|library_strategy|Sequencing strategy, e.g., whole genome sequencing (`WGS`). [See ENA permitted values](https://ena-docs.readthedocs.io/en/latest/submit/reads/webin-cli.html#strategy), 
|library_description| Unique descriptor for library| 
|"uploaded file 1"|Gzipped forward filepath - `uploaded.file.1`|
|"uploaded file 2"|Gzipped reverse filepath - `uploaded.file.2`| 


**To generate that TSV:**

1. CSV: ENA registered sample metadata - this can be downloaded directly from the ENA webin site (must contain at minimum sample accession (`sample_accession`) and unique sample name - in this case we use `sample_alias`) 

<p align="center">
  <img src="https://github.com/museomics/ukbol_submissions/blob/main/img/ENA_sample_download.png" width="400" height="300"
    alt="ENA Webin Sample metadata download">
</p

2. CSV: Sequence filepaths - this must have a minimum of 3 columns, unique sample name (`sample_alias`), forward read filepath (`uploaded.file.1`) and reverse read filepath (`uploaded.file.2`)

To generate the TSV run the R code [submit_reads.R](https://github.com/museomics/ukbol_submissions/blob/main/submit_reads.R)- where you change defined variables according to needs.

Once this TSV is generated, it can be **validated** and then **submitted** to ENA via the [ena bulk webincli tool](https://github.com/enasequence/ena-bulk-webincli/tree/master).
This tool takes the TSV and generates individual manifests before submitting the manifests and sequence data to ENA. 

To validate the TSV and generate the manifests the command would look like the following: 
```
python /path/to/ena-bulk-webincli/bulk_webincli.py -u Webin-XXXXX -p XXXXXX -g reads -s sequence_submission.tsv -m validate -d UKBOL_accelerated --webinCliPath /path/to/ena-bulk-webincli/webin-cli-9.0.1.jar
```

**NOTE** You will have to specify the filepath to bulk_webincli.py based on where your install is. You will also have to specify your webin login details (`-u` and `-p` for username and password). The argument `-d` specifies the parent directory of your files to be uploaded
To submit the manifests run change `-m validate` to `-m submit`: 

```
python /path/to/ena-bulk-webincli/bulk_webincli.py -u Webin-XXXXX -p XXXXXX -g reads -s sequence_submission.tsv -m submit -d UKBOL_accelerated --webinCliPath /path/to/ena-bulk-webincli/webin-cli-9.0.1.jar
```

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
