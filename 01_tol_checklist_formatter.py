#!/usr/bin/env python3
"""
ENA Tree of Life Checklist Formatter (01_tol_checklist_formatter.py)
====================================================================

Builds the ENA Tree of Life sample checklist (ERC000053) for samples whose taxa
have an ENA taxid, by joining the original specimen metadata to the taxids found
by the taxid-minting workflow (https://github.com/museomics/taxid-minting-process).

This is the first script of the sample registration workflow, run AFTER taxid
minting. One checklist row is written per sample (keyed by Process ID); only
samples with a taxid are included. Every other sample in the batch is written to
a "not included" file with the reason, so the totals always reconcile.

WHERE EACH SAMPLE'S TAXID COMES FROM (first match wins)
--------------------------------------------------------
1. 01_ena_taxid_check.py  *-ena_matches.csv  -> matched by ID
       (ena_taxid_1, ena_scientificName_1)
2. 04_post_ver_ena_check.py *-ena_matches.csv -> matched by ID
       (ena_taxid_2, ena_scientificName_2)
3. 04 matches by NAME: manually verified sheets are usually deduplicated to one
   row per species, so most specimens never went through 04. Using --verified,
   each original scientificName is mapped to its confirmed_taxonomy, and the
   04 match for that confirmed name is applied to every specimen of it.
4. (--query-ena) ENA suggest-for-submission v2 lookup of the name that was sent
   for minting, to pick up taxids minted since the request forms were sent:
     - verified species:            confirmed_taxonomy
     - reduced to genus at verification ('Genus sp.'): 'Genus sp. {ID}'
     - other species-level samples: scientificName (from 00 species file)
     - genus-level and above:       '{scientificName} sp. {ID}' (from 00 non-species)
   Only an exact (case-insensitive), submittable scientificName match is used;
   more than one exact match is treated as ambiguous and not used.

Disagreements between sources are logged.

NAME TRIMMING (for matching only)
---------------------------------
Original names often carry qualifiers or codes that were removed before the
name was requested (e.g. 'Troglochthonius doratodactylus GP' was requested as
'Troglochthonius doratodactylus'). When matching samples to request forms and
looking names up on ENA, the script also tries a trimmed name:
  - removes qualifiers: cf., aff., nr., near, s.l., s.s., s.str., s.lat., sensu
    lato/stricto, agg., complex, group, gr., grp. (with or without the full stop)
  - removes bracketed text, e.g. authorities '(Pennant, 1777)' or '(nom. inval.)'
  - keeps genus + epithet (+ a lower-case subspecies) and drops anything after,
    e.g. population codes (GP, GB, SJ)
  - names whose 'epithet' is not a proper lower-case word (e.g. 'Eunice sp2')
    are not trimmed to a species
The name registered in the checklist is always ENA's name for the taxid.
Request-form names in the form 'Genus sp. {ID}' are also matched by the ID, so a
sample is recognised even if its genus was changed at verification.

WHY A SAMPLE IS NOT INCLUDED (column 'reason' of *_not_included.csv)
---------------------------------------------------------------------
Each batch sample without a taxid gets the first reason that applies:
  requested (non-species form) / requested (species form)
        the name sent for minting is on a --request-form file; waiting for ENA
  verification: confirmed_taxonomy empty
        04 status MAN_VER_NAME_EMPTY, or the verified sheet has no confirmed name
  possible homonym (04) / possible homonym (01)
        MATCH_PHYLUM_UNCHECKED or TAXONOMIC_MISMATCH_HOMONYM, and not requested
  ENA error (01/04)
        API_ERROR status in 01 or 04
  conflicting confirmed names
        the original name maps to more than one confirmed name in the verified sheets
  not on any request form   (only when --request-form files are given)
  no taxid yet              (otherwise)
  Process ID not found in metadata
        has a taxid, but no row in the metadata file
With --query-ena the lookup result is appended, e.g. '; ENA lookup: not found in ENA'.
Note: not-included rows are per specimen, whereas species request forms list each
name once, so the two counts are not expected to match.

CHECKLIST FORMATTING
--------------------
- scientific_name and sample_description = ENA scientific name for the taxid
- sample_alias = Process ID
- sample_title = 'Voucher: {specimen_voucher}; Sample ID: {Sample ID}'
- project name = --project
- collection date -> ISO 8601 (YYYY-MM-DD; partial dates kept as YYYY-MM / YYYY).
  Unreadable or implausible dates (in the future, or before 1700) become
  'missing: third party data' and are listed in the log.
- lifestage -> ENA's controlled list (adult, egg, embryo, gametophyte, juvenile,
  larva, zygote, vegetative structure, vegetative cell, sporophyte,
  spore-bearing structure, pupa, not provided, not collected, not applicable).
  Known variants are mapped (e.g. Adult/a/flowering/polyp/medusa -> adult;
  immature/subadult/tritonymph -> juvenile; larvae/metacercaria -> larva;
  pupae -> pupa; female/male -> adult); anything else becomes
  'missing: third party data' and is logged.
- geographic location (country and/or sea) -> ENA's country list. Known variants
  are mapped (e.g. Turkiye -> Turkey, United States -> USA); placeholders such as
  'Unspecified country' become 'missing: third party data'; any value still not
  on ENA's list is kept as recorded and logged.
- sex is free text and is kept as recorded.
- latitude/longitude -> decimal degrees, max 8 dp, range-checked
- Empty / NaN / N/A / na / none / not collected -> 'missing: third party data'
- Mandatory fields (organism part, lifestage, project name, collected_by,
  collection date, geographic location (region and locality), habitat, sex,
  geographic location (country and/or sea), collecting institution) are never
  blank: missing values, or a source column absent from the metadata, become
  'missing: third party data' (counted in the log).
- Tabs and line breaks inside values are replaced by single spaces.

INPUTS (all CSV, TSV or XLSX)
-----------------------------
  -m/--metadata     original sample metadata (may contain other samples too)
  --species         00_filter_taxonomy *_species.csv (defines batch, repeatable)
  --non-species     00_filter_taxonomy *_non_species.csv (optional, repeatable)
                    If an ID appears in more than one batch file (e.g. a sample
                    re-run through 00), a species-level entry wins over a
                    genus-level one, and otherwise the file given later wins.
  --ena1            01 *-ena_matches.csv (repeatable)
  --ena2            04 *-ena_matches.csv (optional, repeatable)
  --verified        manually verified sheet(s) given to 04 (optional, repeatable)
  --request-form    taxid request TSV(s) submitted to ENA (optional, repeatable)
  --ena1-status     any 01 output with ID + ena_status_1, e.g. the combined
                    output (optional, repeatable)
  --ena2-status     any 04 output with ID + ena_status_2 (optional, repeatable)

OUTPUTS
-------
  {output}_tol_checklist.csv    checklist, one row per included sample (UTF-8)
  {output}_not_included.csv     batch samples not included, with reason and Sample ID
  {output}_tol_checklist.log    processing log and reconciliation

USAGE
-----
  python 01_tol_checklist_formatter.py \\
      -m sample_metadata.csv \\
      --species 00_filter_taxonomy_out_species.csv \\
      --non-species 00_filter_taxonomy_out_non_species.csv \\
      --ena1 01_ena_check_species-ena_matches.csv \\
      --ena2 04_ena_post_ver-ena_matches.csv \\
      --verified 03_gbif_processor_manually_verify-complete.xlsx \\
      -p BGE -o ./sample_registration/BGE_batch1 [--query-ena]

Author: Dan Parsons @NHMUK
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

MISSING = 'missing: third party data'
EMPTY_VALUES = {'', 'nan', 'none', 'null', 'n/a', 'na', 'not collected', 'nat', 'missing'}

ENA_V2_URL = 'https://www.ebi.ac.uk/ena/taxonomy/rest/v2/suggest-for-submission/{name}'

# Checklist columns (order as in the Tree of Life checklist template)
CHECKLIST_COLUMNS = [
    'tax_id', 'scientific_name', 'sample_alias', 'sample_title', 'sample_description',
    'organism part', 'lifestage', 'project name', 'collected_by', 'collection date',
    'geographic location (latitude)', 'geographic location (longitude)',
    'geographic location (region and locality)', 'geographic location (country and/or sea)',
    'habitat', 'sex', 'collecting institution', 'specimen_voucher',
]

MANDATORY_COLUMNS = [
    'organism part', 'lifestage', 'project name', 'collected_by', 'collection date',
    'geographic location (region and locality)', 'habitat', 'sex',
    'geographic location (country and/or sea)', 'collecting institution',
]

LIFESTAGE_VALUES = ['adult', 'egg', 'embryo', 'gametophyte', 'juvenile', 'larva', 'zygote',
                    'vegetative structure', 'vegetative cell', 'sporophyte',
                    'spore-bearing structure', 'pupa', 'not provided', 'not collected',
                    'not applicable', MISSING]
LIFESTAGE_MAP = {
    'a': 'adult', 'adults': 'adult', 'flowering': 'adult', 'polyp': 'adult', 'medusa': 'adult',
    'polygastric': 'adult',
    'juvenil': 'juvenile', 'juveniles': 'juvenile', 'immature': 'juvenile', 'subadult': 'juvenile',
    'sub-adult': 'juvenile', 'tritonymph': 'juvenile',
    'larvae': 'larva', 'metacercaria': 'larva',
    'pupae': 'pupa',
    'female': 'adult', 'male': 'adult', 'females': 'adult', 'males': 'adult',
}

# ENA's accepted values for 'geographic location (country and/or sea)' (as in sample_registration.R)
ENA_COUNTRIES = [
    'Afghanistan', 'Albania', 'Algeria', 'American Samoa', 'Andorra', 'Angola', 'Anguilla',
    'Antarctica', 'Antigua and Barbuda', 'Arctic Ocean', 'Argentina', 'Armenia', 'Aruba',
    'Ashmore and Cartier Islands', 'Atlantic Ocean', 'Australia', 'Austria', 'Azerbaijan',
    'Bahamas', 'Bahrain', 'Baker Island', 'Baltic Sea', 'Bangladesh', 'Barbados',
    'Bassas da India', 'Belarus', 'Belgium', 'Belize', 'Benin', 'Bermuda', 'Bhutan', 'Bolivia',
    'Borneo', 'Bosnia and Herzegovina', 'Botswana', 'Bouvet Island', 'Brazil',
    'British Virgin Islands', 'Brunei', 'Bulgaria', 'Burkina Faso', 'Burundi', 'Cambodia',
    'Cameroon', 'Canada', 'Cape Verde', 'Cayman Islands', 'Central African Republic', 'Chad',
    'Chile', 'China', 'Christmas Island', 'Clipperton Island', 'Cocos Islands', 'Colombia',
    'Comoros', 'Cook Islands', 'Coral Sea Islands', 'Costa Rica', "Cote d'Ivoire", 'Croatia',
    'Cuba', 'Curacao', 'Cyprus', 'Czechia', 'Czech Republic',
    'Democratic Republic of the Congo', 'Denmark', 'Djibouti', 'Dominica', 'Dominican Republic',
    'Ecuador', 'Egypt', 'El Salvador', 'Equatorial Guinea', 'Eritrea', 'Estonia', 'Eswatini',
    'Ethiopia', 'Europa Island', 'Falkland Islands (Islas Malvinas)', 'Faroe Islands', 'Fiji',
    'Finland', 'France', 'French Guiana', 'French Polynesia',
    'French Southern and Antarctic Lands', 'Gabon', 'Gambia', 'Gaza Strip', 'Georgia',
    'Germany', 'Ghana', 'Gibraltar', 'Glorioso Islands', 'Greece', 'Greenland', 'Grenada',
    'Guadeloupe', 'Guam', 'Guatemala', 'Guernsey', 'Guinea', 'Guinea-Bissau', 'Guyana', 'Haiti',
    'Heard Island and McDonald Islands', 'Honduras', 'Hong Kong', 'Howland Island', 'Hungary',
    'Iceland', 'India', 'Indian Ocean', 'Indonesia', 'Iran', 'Iraq', 'Ireland', 'Isle of Man',
    'Israel', 'Italy', 'Jamaica', 'Jan Mayen', 'Japan', 'Jarvis Island', 'Jersey',
    'Johnston Atoll', 'Jordan', 'Juan de Nova Island', 'Kazakhstan', 'Kenya',
    'Kerguelen Archipelago', 'Kingman Reef', 'Kiribati', 'Kosovo', 'Kuwait', 'Kyrgyzstan',
    'Laos', 'Latvia', 'Lebanon', 'Lesotho', 'Liberia', 'Libya', 'Liechtenstein', 'Line Islands',
    'Lithuania', 'Luxembourg', 'Macau', 'Madagascar', 'Malawi', 'Malaysia', 'Maldives', 'Mali',
    'Malta', 'Marshall Islands', 'Martinique', 'Mauritania', 'Mauritius', 'Mayotte',
    'Mediterranean Sea', 'Mexico', 'Micronesia, Federated States of', 'Midway Islands',
    'Moldova', 'Monaco', 'Mongolia', 'Montenegro', 'Montserrat', 'Morocco', 'Mozambique',
    'Myanmar', 'Namibia', 'Nauru', 'Navassa Island', 'Nepal', 'Netherlands', 'New Caledonia',
    'New Zealand', 'Nicaragua', 'Niger', 'Nigeria', 'Niue', 'Norfolk Island', 'North Korea',
    'North Macedonia', 'North Sea', 'Northern Mariana Islands', 'Norway', 'Oman',
    'Pacific Ocean', 'Pakistan', 'Palau', 'Palmyra Atoll', 'Panama', 'Papua New Guinea',
    'Paracel Islands', 'Paraguay', 'Peru', 'Philippines', 'Pitcairn Islands', 'Poland',
    'Portugal', 'Puerto Rico', 'Qatar', 'Republic of the Congo', 'Reunion', 'Romania',
    'Ross Sea', 'Russia', 'Rwanda', 'Saint Barthelemy', 'Saint Helena', 'Saint Kitts and Nevis',
    'Saint Lucia', 'Saint Pierre and Miquelon', 'Saint Vincent and the Grenadines', 'Samoa',
    'San Marino', 'Saint Martin', 'Sao Tome and Principe', 'Saudi Arabia', 'Senegal', 'Serbia',
    'Seychelles', 'Sierra Leone', 'Singapore', 'Sint Maarten', 'Slovakia', 'Slovenia',
    'Solomon Islands', 'Somalia', 'South Africa',
    'South Georgia and the South Sandwich Islands', 'South Korea', 'South Sudan',
    'Southern Ocean', 'Spain', 'Spratly Islands', 'Sri Lanka', 'State of Palestine', 'Sudan',
    'Suriname', 'Svalbard', 'Sweden', 'Switzerland', 'Syria', 'Taiwan', 'Tajikistan',
    'Tanzania', 'Tasman Sea', 'Thailand', 'Timor-Leste', 'Togo', 'Tokelau', 'Tonga',
    'Trinidad and Tobago', 'Tromelin Island', 'Tunisia', 'Turkey', 'Turkmenistan',
    'Turks and Caicos Islands', 'Tuvalu', 'USA', 'Uganda', 'Ukraine', 'United Arab Emirates',
    'United Kingdom', 'Uruguay', 'Uzbekistan', 'Vanuatu', 'Venezuela', 'Viet Nam',
    'Wake Island', 'Virgin Islands', 'Wallis and Futuna', 'West Bank', 'Western Sahara',
    'Yemen', 'Zambia', 'Zimbabwe', 'missing', 'missing: control sample',
    'missing: data agreement established pre-2023', 'missing: endangered species',
    'missing: human-identifiable', 'missing: lab stock', 'missing: sample group',
    'missing: synthetic construct', 'missing: third party data', 'not applicable',
    'not collected', 'not provided', 'restricted access',
]
COUNTRY_MAP = {
    'turkiye': 'Turkey', 'türkiye': 'Turkey',
    'north atlantic ocean': 'Atlantic Ocean', 'south atlantic ocean': 'Atlantic Ocean',
    'united states': 'USA', 'united states of america': 'USA',
    'cabo verde': 'Cape Verde', 'vietnam': 'Viet Nam', 'aland': 'Finland', 'åland': 'Finland',
    'french southern territories': 'French Southern and Antarctic Lands',
    'unspecified country': MISSING, 'unrecoverable': MISSING,
    'exception - zoological park': MISSING,
}

# Checklist column -> metadata column (matched ignoring case, spaces and underscores)
METADATA_SOURCES = {
    'organism part': 'organism_part',
    'lifestage': 'lifestage',
    'collected_by': 'collected_by',
    'collection date': 'collection_date',
    'geographic location (latitude)': 'latitude',
    'geographic location (longitude)': 'longitude',
    'geographic location (region and locality)': 'geographic_location_locality',
    'geographic location (country and/or sea)': 'geographic_location',
    'habitat': 'habitat',
    'sex': 'sex',
    'collecting institution': 'collecting_institution',
    'specimen_voucher': 'specimen_voucher',
}
SAMPLE_ID_SOURCE = 'Sample ID'

logger = logging.getLogger('tol_checklist')


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def setup_logging(log_path):
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(fh)
    logger.addHandler(ch)


def read_table(path):
    """Read a CSV, TSV or XLSX file with every cell kept as-is (strings, or dates from XLSX)."""
    if not Path(path).is_file():
        logger.error(f"File not found: {path}")
        sys.exit(1)
    suffix = Path(path).suffix.lower()
    if suffix in ('.xlsx', '.xlsm'):
        df = pd.read_excel(path, dtype=object)
    elif suffix == '.tsv':
        df = pd.read_csv(path, sep='\t', dtype=str, keep_default_na=False)
    elif suffix == '.csv':
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    else:
        logger.error(f"Unsupported file type '{suffix}' for {path} (use .csv, .tsv or .xlsx)")
        sys.exit(1)
    df = df.dropna(how='all')
    logger.info(f"Read {len(df)} rows from {path}")
    return df


def clean(value):
    """Return a single-line stripped string, or '' for NaN/None."""
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except (TypeError, ValueError):
        pass
    return ' '.join(str(value).split())


def is_missing(value):
    return clean(value).lower() in EMPTY_VALUES


def normalise_value(value):
    """Clean a metadata value, mapping empty/placeholder values to the missing term."""
    text = clean(value)
    if text.lower() in EMPTY_VALUES:
        return MISSING
    if text.lower() == MISSING:
        return MISSING
    return text


def norm_key(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def find_column(df, wanted):
    """Find a column ignoring case, spaces and punctuation. Returns the real name or None."""
    target = norm_key(wanted)
    for col in df.columns:
        if norm_key(col) == target:
            return col
    return None


def clean_taxid(value):
    text = clean(value)
    if re.fullmatch(r'\d+\.0+', text):
        text = text.split('.')[0]
    return text if re.fullmatch(r'\d+', text) else ''


# ---------------------------------------------------------------------------
# Date and coordinate formatting
# ---------------------------------------------------------------------------

def format_date(value):
    """
    Convert a collection date to ISO 8601. Returns (formatted_value, problem_or_None).
    Accepts dd/mm/yyyy, d/m/yyyy, dd-mm-yyyy, dd.mm.yyyy, yyyy-mm-dd, mm/yyyy,
    yyyy-mm, yyyy and Excel dates. Partial dates keep their precision.
    """
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime('%Y-%m-%d'), None
    if isinstance(value, date):
        return value.isoformat(), None
    text = clean(value)
    if text.lower() in EMPTY_VALUES or text.lower() == MISSING:
        return MISSING, None
    if text.lower().startswith('missing:'):
        return text, None

    m = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', text)
    if m:
        d, mo, y = (int(g) for g in m.groups())
        try:
            return date(y, mo, d).isoformat(), None
        except ValueError:
            return MISSING, f"invalid day/month in '{text}'"
    m = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]00:00(?::00)?)?', text)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        try:
            return date(y, mo, d).isoformat(), None
        except ValueError:
            return MISSING, f"invalid date '{text}'"
    m = re.fullmatch(r'(\d{1,2})[/.-](\d{4})', text)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}", None
        return MISSING, f"invalid month in '{text}'"
    m = re.fullmatch(r'(\d{4})-(\d{1,2})', text)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}", None
        return MISSING, f"invalid month in '{text}'"
    if re.fullmatch(r'\d{4}', text):
        return text, None
    return MISSING, f"unrecognised date '{text}'"


def check_date_plausible(formatted, original):
    """Return (value, problem). Dates in the future or before 1700 become the missing term."""
    if formatted.lower().startswith('missing'):
        return formatted, None
    today = date.today()
    if int(formatted[:4]) < 1700:
        return MISSING, f"implausible year in '{original}'"
    limit = {10: today.isoformat(), 7: today.strftime('%Y-%m'), 4: str(today.year)}.get(len(formatted))
    if limit and formatted > limit:
        return MISSING, f"date in the future '{original}'"
    return formatted, None


def format_lifestage(value):
    """Map a lifestage to ENA's controlled list. Returns (value, original_if_not_mappable)."""
    text = normalise_value(value)
    if text == MISSING:
        return MISSING, None
    key = text.lower()
    if key in LIFESTAGE_VALUES:
        return key, None
    if key in LIFESTAGE_MAP:
        return LIFESTAGE_MAP[key], None
    return MISSING, text


ENA_COUNTRY_LOOKUP = {c.lower(): c for c in ENA_COUNTRIES}


def format_country(value):
    """Map a country/sea to ENA's list. Returns (value, change_note_or_None, still_invalid)."""
    text = normalise_value(value)
    key = text.lower()
    if key in COUNTRY_MAP:
        return COUNTRY_MAP[key], f"'{text}' -> '{COUNTRY_MAP[key]}'", False
    if key in ENA_COUNTRY_LOOKUP:
        fixed = ENA_COUNTRY_LOOKUP[key]
        return fixed, (f"'{text}' -> '{fixed}'" if fixed != text else None), False
    return text, None, True


def format_coordinate(value, limit):
    """Return (formatted_value, problem_or_None) for a decimal-degree coordinate."""
    text = clean(value)
    if text.lower() in EMPTY_VALUES or text.lower() == MISSING:
        return MISSING, None
    candidate = text.replace(',', '.') if text.count(',') == 1 and '.' not in text else text
    try:
        number = float(candidate)
    except ValueError:
        return MISSING, f"not a decimal number '{text}'"
    if not -limit <= number <= limit:
        return MISSING, f"out of range '{text}'"
    formatted = f"{round(number, 8):.8f}".rstrip('0').rstrip('.')
    return ('0' if formatted in ('-0', '') else formatted), None


# ---------------------------------------------------------------------------
# Loading the taxid-minting outputs
# ---------------------------------------------------------------------------

def load_batch(species_files, non_species_files):
    """Return an ordered dict ID -> {'scientificName', 'level'} for every batch sample."""
    batch = {}
    for level, files in (('species', species_files), ('non_species', non_species_files)):
        for path in files or []:
            df = read_table(path)
            id_col, name_col = find_column(df, 'ID'), find_column(df, 'scientificName')
            if not id_col or not name_col:
                logger.error(f"{path} needs 'ID' and 'scientificName' columns (00_filter_taxonomy output)")
                sys.exit(1)
            for _, row in df.iterrows():
                sid = clean(row[id_col])
                if not sid:
                    continue
                entry = {'scientificName': clean(row[name_col]), 'level': level}
                if sid in batch:
                    old = batch[sid]
                    if old['level'] == 'species' and level == 'non_species':
                        logger.warning(f"ID {sid} is in a species file ('{old['scientificName']}') and a "
                                       f"non-species file ('{entry['scientificName']}') - species entry kept")
                        continue
                    logger.warning(f"ID {sid} appears more than once in the batch files - "
                                   f"'{old['scientificName']}' replaced by '{entry['scientificName']}' from {path}")
                batch[sid] = entry
    return batch


def load_matches(files, taxid_col, name_col, status_col, label):
    """
    Load ENA match files. Returns (by_id, by_name):
      by_id   ID -> (taxid, ena_name)
      by_name searched/confirmed name (lower case) -> set of (taxid, ena_name)
    """
    by_id, by_name = {}, defaultdict(set)
    for path in files or []:
        df = read_table(path)
        cols = {k: find_column(df, k) for k in ('ID', taxid_col, name_col, status_col,
                                                 'ena_search_term_2', 'confirmed_taxonomy')}
        if not cols['ID'] or not cols[taxid_col] or not cols[name_col]:
            logger.error(f"{path} needs 'ID', '{taxid_col}' and '{name_col}' columns ({label} output)")
            sys.exit(1)
        kept = 0
        for _, row in df.iterrows():
            if cols[status_col] and clean(row[cols[status_col]]) != 'MATCH_TAXONOMICALLY_CONSISTENT':
                continue
            taxid, ena_name = clean_taxid(row[cols[taxid_col]]), clean(row[cols[name_col]])
            sid = clean(row[cols['ID']])
            if not taxid or not ena_name:
                continue
            kept += 1
            if sid:
                if sid in by_id and by_id[sid][0] != taxid:
                    logger.warning(f"{label}: ID {sid} has two different taxids "
                                   f"({by_id[sid][0]}, {taxid}) - first kept")
                by_id.setdefault(sid, (taxid, ena_name))
            for key_col in ('ena_search_term_2', 'confirmed_taxonomy'):
                if cols[key_col]:
                    key = clean(row[cols[key_col]]).lower()
                    if key:
                        by_name[key].add((taxid, ena_name))
        logger.info(f"{label}: {kept} matched rows used from {path}")
    return by_id, by_name


def load_verified(files):
    """
    Load manually verified sheets. Returns (by_id, by_name, info):
      by_id   ID -> confirmed_taxonomy
      by_name original scientificName (lower case) -> confirmed_taxonomy (unique only)
      info    {'empty_ids', 'empty_names', 'conflict_names'} used to explain
              why a sample has no taxid
    """
    by_id, name_sets = {}, defaultdict(set)
    empty_ids, empty_names = set(), set()
    for path in files or []:
        df = read_table(path)
        id_col = find_column(df, 'ID')
        sci_col = find_column(df, 'scientificName')
        ct_col = find_column(df, 'confirmed_taxonomy')
        if not ct_col or not sci_col:
            logger.error(f"{path} needs 'scientificName' and 'confirmed_taxonomy' columns")
            sys.exit(1)
        for _, row in df.iterrows():
            ct = clean(row[ct_col])
            if not ct or is_missing(ct):
                if id_col and clean(row[id_col]):
                    empty_ids.add(clean(row[id_col]))
                if clean(row[sci_col]):
                    empty_names.add(clean(row[sci_col]).lower())
                continue
            if id_col and clean(row[id_col]):
                by_id[clean(row[id_col])] = ct
            sci = clean(row[sci_col]).lower()
            if sci:
                name_sets[sci].add(ct)
    by_name, conflict_names = {}, set()
    for sci, cts in name_sets.items():
        if len(cts) == 1:
            by_name[sci] = next(iter(cts))
        else:
            conflict_names.add(sci)
            logger.warning(f"Verified sheets map '{sci}' to more than one confirmed name "
                           f"{sorted(cts)} - not used for specimens without their own row")
    info = {'empty_ids': empty_ids - set(by_id), 'empty_names': empty_names - set(name_sets),
            'conflict_names': conflict_names}
    return by_id, by_name, info


def norm_name(name):
    return ' '.join(clean(name).split()).lower()


QUALIFIER_TOKENS = {'cf', 'aff', 'nr', 'near', 'sl', 's.l', 'ss', 's.s', 's.str', 'sstr', 's.lat',
                    'slat', 'sensu', 'lato', 'stricto', 'agg', 'complex', 'group', 'gr', 'grp'}


def trim_name(name):
    """
    Reduce a species name to genus + epithet (+ lower-case subspecies), dropping
    qualifiers (cf., aff., s.l. ...), bracketed text and trailing codes.
    Returns '' if no valid species name remains.
    """
    text = re.sub(r'\([^)]*\)', ' ', clean(name))
    words = []
    for token in text.split():
        bare = token.strip('.,;:').lower()
        if bare in QUALIFIER_TOKENS or token.lower().rstrip('.') in QUALIFIER_TOKENS:
            continue
        words.append(token.strip(',;:'))
    if len(words) < 2 or not re.fullmatch(r'[A-Z][a-z]+(?:-[a-z]+)?', words[0]):
        return ''
    kept = [words[0]]
    for word in words[1:3]:
        if re.fullmatch(r'[a-z][a-z]+(?:-[a-z]+)*', word) and word not in ('sp', 'spp', 'var', 'subsp', 'ssp', 'f'):
            kept.append(word)
        else:
            break
    return ' '.join(kept) if len(kept) >= 2 else ''


def load_request_forms(files):
    """
    Return (names, by_id):
      names  {normalised proposed_name: ('non-species form' | 'species form', name as written)}
      by_id  {lower-case ID: normalised name} for names of the form 'Genus sp. {ID}'
    """
    names, by_id = {}, {}
    for path in files or []:
        df = read_table(path)
        name_col, type_col = find_column(df, 'proposed_name'), find_column(df, 'name_type')
        if not name_col:
            logger.error(f"{path} needs a 'proposed_name' column (taxid request form)")
            sys.exit(1)
        for _, row in df.iterrows():
            written = ' '.join(clean(row[name_col]).split())
            name = written.lower()
            if not name or name == 'proposed_name':
                continue
            name_type = clean(row[type_col]).lower() if type_col else ''
            id_match = re.fullmatch(r'\S+ sp\. (\S+)', name)
            non_species = 'unidentified' in name_type or id_match
            names[name] = ('non-species form' if non_species else 'species form', written)
            if id_match:
                by_id[id_match.group(1)] = name
        logger.info(f"Request form names loaded so far: {len(names)}")
    return names, by_id


def match_request_form(sid, sample, name, confirmed, forms, forms_by_id):
    """
    Find the request-form name this sample was requested under.
    Tries the candidate, original and confirmed names (and 'Genus sp. ID' for
    genus-level samples), then their trimmed versions, then a 'Genus sp. {ID}'
    form name with this sample's ID. Returns the normalised form name or ''.
    """
    sci = sample['scientificName']
    candidates = [name, sci, confirmed]
    if sample['level'] == 'non_species':
        candidates.append(f"{sci} sp. {sid}")
    candidates += [trim_name(c) for c in candidates if c]
    for cand in candidates:
        key = norm_name(cand) if cand else ''
        if key and key in forms:
            return key
    return forms_by_id.get(sid.lower(), '')


def load_statuses(files, status_col, label):
    """Return {ID: set of statuses} from any 01/04 output files."""
    statuses = defaultdict(set)
    for path in files or []:
        df = read_table(path)
        id_col, st_col = find_column(df, 'ID'), find_column(df, status_col)
        if not id_col or not st_col:
            logger.error(f"{path} needs 'ID' and '{status_col}' columns ({label} output)")
            sys.exit(1)
        for _, row in df.iterrows():
            sid, status = clean(row[id_col]), clean(row[st_col])
            if sid and status:
                statuses[sid].add(status)
    return statuses


HOMONYM_STATUSES = {'MATCH_PHYLUM_UNCHECKED', 'TAXONOMIC_MISMATCH_HOMONYM'}


def classify_reason(sid, sample, confirmed, verified_info, forms, form_key, status1, status2):
    """
    Explain why a sample has no taxid. Returns (reason, matched_form_name).
    See 'WHY A SAMPLE IS NOT INCLUDED' in the module docstring.
    """
    sci = sample['scientificName']
    if form_key:
        return f"requested ({forms[form_key][0]})", form_key
    s1, s2 = status1.get(sid, set()), status2.get(sid, set())
    if ('MAN_VER_NAME_EMPTY' in s2 or sid in verified_info['empty_ids']
            or (not confirmed and sci.lower() in verified_info['empty_names'])):
        return 'verification: confirmed_taxonomy empty', ''
    if s2 & HOMONYM_STATUSES:
        return 'possible homonym (04)', ''
    if s1 & HOMONYM_STATUSES:
        return 'possible homonym (01)', ''
    if any(s.startswith('API_ERROR') for s in s1 | s2):
        return 'ENA error (01/04)', ''
    if not confirmed and sci.lower() in verified_info['conflict_names']:
        return 'conflicting confirmed names', ''
    return ('not on any request form' if forms else 'no taxid yet'), ''


# ---------------------------------------------------------------------------
# ENA v2 lookup
# ---------------------------------------------------------------------------

class EnaLookup:
    """Exact-name lookups against ENA suggest-for-submission v2, cached per name."""

    def __init__(self, min_delay=0.04, retries=3, retry_delay=2):
        self.cache = {}
        self.min_delay = min_delay
        self.retries = retries
        self.retry_delay = retry_delay
        self.last_call = 0.0

    def lookup(self, name):
        """Return (taxid, ena_name, problem). problem is None when a unique exact match is found."""
        key = name.lower()
        if key not in self.cache:
            self.cache[key] = self._query(name)
        return self.cache[key]

    def _query(self, name):
        url = ENA_V2_URL.format(name=urllib.parse.quote(name))
        for attempt in range(1, self.retries + 1):
            wait = self.min_delay - (time.time() - self.last_call)
            if wait > 0:
                time.sleep(wait)
            self.last_call = time.time()
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 404:
                    return '', '', 'not found in ENA'
                response.raise_for_status()
                payload = response.json()
                break
            except (requests.RequestException, ValueError) as exc:
                if attempt == self.retries:
                    return '', '', f'ENA API error: {exc}'
                logger.warning(f"ENA lookup failed for '{name}' ({exc}) - retrying")
                time.sleep(self.retry_delay)
        results = payload.get('_embedded', {}).get('taxonSuggestDtoList', []) if isinstance(payload, dict) else payload
        exact = {}
        for hit in results or []:
            if clean(hit.get('scientificName')).lower() == name.lower() and hit.get('submittable', True) in (True, 'true'):
                taxid = clean_taxid(hit.get('taxId'))
                if taxid:
                    exact[taxid] = clean(hit.get('scientificName'))
        if not exact:
            return '', '', 'not found in ENA'
        if len(exact) > 1:
            return '', '', f'ambiguous: {len(exact)} exact ENA matches ({", ".join(sorted(exact))})'
        taxid, ena_name = next(iter(exact.items()))
        return taxid, ena_name, None


# ---------------------------------------------------------------------------
# Taxid resolution
# ---------------------------------------------------------------------------

def candidate_name(sid, sample, verified_by_id, verified_by_name):
    """The name that was sent to ENA for minting (used for the v2 lookup)."""
    confirmed = verified_by_id.get(sid) or verified_by_name.get(sample['scientificName'].lower())
    if confirmed:
        if re.fullmatch(r'\S+ sp\.?', confirmed):
            return f"{confirmed.split()[0]} sp. {sid}"
        return confirmed
    if sample['level'] == 'non_species':
        return f"{sample['scientificName']} sp. {sid}"
    return sample['scientificName']


def resolve_taxids(batch, ena1, ena2, verified, ena_lookup, forms, status1, status2):
    forms, forms_by_id = forms
    """
    Return (resolved, pending, stats).
      resolved: ID -> (taxid, ena_name, source)
      pending:  ID -> (reason, candidate name, queried 'yes'/'no', matched form name)
    """
    ena1_by_id, _ = ena1
    ena2_by_id, ena2_by_name = ena2
    verified_by_id, verified_by_name, verified_info = verified
    resolved, pending, stats = {}, {}, Counter()

    for sid, sample in batch.items():
        found = []
        if sid in ena1_by_id:
            found.append((*ena1_by_id[sid], '01 ENA match (ID)'))
        if sid in ena2_by_id:
            found.append((*ena2_by_id[sid], '04 ENA match (ID)'))
        confirmed = verified_by_id.get(sid) or verified_by_name.get(sample['scientificName'].lower())
        if confirmed and confirmed.lower() in ena2_by_name:
            hits = ena2_by_name[confirmed.lower()]
            if len({t for t, _ in hits}) == 1:
                found.append((*next(iter(hits)), '04 ENA match (confirmed name)'))
            else:
                logger.warning(f"{sid}: confirmed name '{confirmed}' has several 04 taxids {sorted(hits)} - not used")

        if found:
            taxid, ena_name, source = found[0]
            others = {t for t, _, _ in found[1:] if t != taxid}
            if others:
                logger.warning(f"{sid}: taxid sources disagree - using {taxid} ({source}); "
                               f"also found {sorted(others)}")
                stats['conflicting sources'] += 1
            resolved[sid] = (taxid, ena_name, source)
            stats[source] += 1
            continue

        name = candidate_name(sid, sample, verified_by_id, verified_by_name)
        form_key = match_request_form(sid, sample, name, confirmed, forms, forms_by_id)
        lookup_note, queried = '', 'no'
        if ena_lookup is not None and name:
            queried = 'yes'
            # Query the name as requested on the form first, then the candidate, then its trimmed form
            query_names = []
            for q in ((forms[form_key][1] if form_key else ''), name, trim_name(name)):
                if q and q.lower() not in [x.lower() for x in query_names]:
                    query_names.append(q)
            taxid = ena_name = problem = ''
            for q in query_names:
                taxid, ena_name, problem = ena_lookup.lookup(q)
                if taxid and ' sp. ' in q and not ena_name.endswith(f" sp. {sid}"):
                    taxid, problem = '', f"ENA name '{ena_name}' does not end in ID {sid}"
                if taxid:
                    break
            if taxid:
                resolved[sid] = (taxid, ena_name, 'ENA v2 lookup')
                stats['ENA v2 lookup'] += 1
                continue
            lookup_note = f"; ENA lookup: {problem}"
        reason, form_name = classify_reason(sid, sample, confirmed, verified_info,
                                            forms, form_key, status1, status2)
        pending[sid] = (reason + lookup_note, name, queried, form_name)
    return resolved, pending, stats


# ---------------------------------------------------------------------------
# Checklist building
# ---------------------------------------------------------------------------

def build_checklist(metadata, id_col, resolved, project, batch_order):
    """Return (checklist rows, not-found IDs, stats)."""
    source_cols = {}
    for checklist_col, meta_name in METADATA_SOURCES.items():
        source_cols[checklist_col] = find_column(metadata, meta_name)
        if not source_cols[checklist_col]:
            logger.warning(f"Metadata has no '{meta_name}' column - '{checklist_col}' will be '{MISSING}' for every sample")
    sample_id_col = find_column(metadata, SAMPLE_ID_SOURCE)
    if not sample_id_col:
        logger.warning(f"Metadata has no '{SAMPLE_ID_SOURCE}' column - sample_title will use '{MISSING}'")

    meta_rows = {}
    duplicates = Counter()
    for _, row in metadata.iterrows():
        sid = clean(row[id_col])
        if not sid:
            continue
        if sid in meta_rows:
            duplicates[sid] += 1
            continue
        meta_rows[sid] = row
    for sid, n in duplicates.items():
        if sid in resolved:
            logger.warning(f"Process ID {sid} appears {n + 1} times in metadata - first row used")

    rows, not_found = [], []
    missing_fills, date_fixes, coord_fixes = Counter(), [], []
    lifestage_unmapped, country_changes, country_invalid = Counter(), Counter(), Counter()
    for sid in batch_order:
        if sid not in resolved:
            continue
        if sid not in meta_rows:
            not_found.append(sid)
            continue
        meta = meta_rows[sid]
        taxid, ena_name, _ = resolved[sid]

        def get(checklist_col):
            col = source_cols[checklist_col]
            return meta[col] if col else ''

        out = {'tax_id': taxid, 'scientific_name': ena_name, 'sample_alias': sid,
               'sample_description': ena_name, 'project name': project}
        for col in ('organism part', 'collected_by',
                    'geographic location (region and locality)', 'habitat', 'sex',
                    'collecting institution', 'specimen_voucher'):
            out[col] = normalise_value(get(col))

        out['lifestage'], unmapped = format_lifestage(get('lifestage'))
        if unmapped:
            lifestage_unmapped[unmapped] += 1
        out['geographic location (country and/or sea)'], change, invalid = format_country(
            get('geographic location (country and/or sea)'))
        if change:
            country_changes[change] += 1
        if invalid:
            country_invalid[out['geographic location (country and/or sea)']] += 1

        raw_date = get('collection date')
        out['collection date'], problem = format_date(raw_date)
        if not problem:
            out['collection date'], problem = check_date_plausible(out['collection date'], clean(raw_date))
        if problem:
            date_fixes.append(f"{sid}: {problem}")
        for col, limit in (('geographic location (latitude)', 90), ('geographic location (longitude)', 180)):
            out[col], problem = format_coordinate(get(col), limit)
            if problem:
                coord_fixes.append(f"{sid} {col}: {problem}")

        sample_id = normalise_value(meta[sample_id_col]) if sample_id_col else MISSING
        out['sample_title'] = f"Voucher: {out['specimen_voucher']}; Sample ID: {sample_id}"

        for col in MANDATORY_COLUMNS:
            if not out[col]:
                out[col] = MISSING
            if out[col] == MISSING:
                missing_fills[col] += 1
        rows.append(out)

    sample_ids = {sid: (normalise_value(row[sample_id_col]) if sample_id_col else MISSING)
                  for sid, row in meta_rows.items()}
    stats = {'missing_fills': missing_fills, 'date_fixes': date_fixes,
             'coord_fixes': coord_fixes, 'metadata_rows': len(meta_rows),
             'lifestage_unmapped': lifestage_unmapped, 'country_changes': country_changes,
             'country_invalid': country_invalid, 'sample_ids': sample_ids,
             'outside_batch': len(set(meta_rows) - set(batch_order))}
    return rows, not_found, stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Build the ENA Tree of Life checklist (CSV) for samples with ENA taxids, '
                    'using the metadata and the taxid-minting workflow outputs.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-m', '--metadata', required=True, help='Original sample metadata (CSV/TSV/XLSX)')
    parser.add_argument('--id-col', default='Process ID', help="Metadata column holding the Process ID (default: 'Process ID')")
    parser.add_argument('--species', required=True, action='append', help='00_filter_taxonomy *_species.csv (repeatable)')
    parser.add_argument('--non-species', action='append', default=[], help='00_filter_taxonomy *_non_species.csv (repeatable)')
    parser.add_argument('--ena1', required=True, action='append', help='01 *-ena_matches.csv (repeatable)')
    parser.add_argument('--ena2', action='append', default=[], help='04 *-ena_matches.csv (repeatable)')
    parser.add_argument('--verified', action='append', default=[], help='Manually verified sheet(s) given to 04 (repeatable)')
    parser.add_argument('--request-form', action='append', default=[], help='Taxid request TSV(s) submitted to ENA, to explain pending samples (repeatable)')
    parser.add_argument('--ena1-status', action='append', default=[], help='Any 01 output with ID + ena_status_1, e.g. the combined output (repeatable)')
    parser.add_argument('--ena2-status', action='append', default=[], help='Any 04 output with ID + ena_status_2, e.g. the combined output (repeatable)')
    parser.add_argument('--query-ena', action='store_true', help='Look up still-pending samples on ENA suggest-for-submission v2')
    parser.add_argument('-p', '--project', required=True, help="Value for 'project name' (e.g. BGE)")
    parser.add_argument('-o', '--output', required=True, help='Output base path, e.g. ./out/BGE_batch1')
    args = parser.parse_args()

    out_base = Path(args.output)
    if out_base.suffix.lower() in ('.csv', '.tsv'):
        out_base = out_base.with_suffix('')
    if out_base.parent and not out_base.parent.exists():
        out_base.parent.mkdir(parents=True, exist_ok=True)
    checklist_path = Path(f"{out_base}_tol_checklist.csv")
    not_included_path = Path(f"{out_base}_not_included.csv")
    setup_logging(f"{out_base}_tol_checklist.log")

    logger.info('=' * 70)
    logger.info('ENA Tree of Life Checklist Formatter')
    logger.info('=' * 70)
    logger.info(f"Started: {datetime.now():%Y-%m-%d %H:%M:%S} | project: {args.project}")

    metadata = read_table(args.metadata)
    id_col = find_column(metadata, args.id_col)
    if not id_col:
        logger.error(f"Metadata has no '{args.id_col}' column. Columns: {list(metadata.columns)}")
        sys.exit(1)

    batch = load_batch(args.species, args.non_species)
    logger.info(f"Batch: {len(batch)} samples "
                f"({sum(s['level'] == 'species' for s in batch.values())} species-level, "
                f"{sum(s['level'] == 'non_species' for s in batch.values())} genus-level or above)")

    ena1 = load_matches(args.ena1, 'ena_taxid_1', 'ena_scientificName_1', 'ena_status_1', '01')
    ena2 = load_matches(args.ena2, 'ena_taxid_2', 'ena_scientificName_2', 'ena_status_2', '04')
    verified = load_verified(args.verified)
    forms = load_request_forms(args.request_form)
    status1 = load_statuses(args.ena1_status, 'ena_status_1', '01')
    status2 = load_statuses(args.ena2_status, 'ena_status_2', '04')

    lookup = EnaLookup() if args.query_ena else None
    resolved, pending, source_stats = resolve_taxids(batch, ena1, ena2, verified, lookup,
                                                     forms, status1, status2)

    rows, not_found, stats = build_checklist(metadata, id_col, resolved, args.project, list(batch))

    with open(checklist_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CHECKLIST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    not_included = []
    for sid, sample in batch.items():
        if sid in pending:
            reason, name, queried, form_name = pending[sid]
        elif sid in not_found:
            reason, name, queried, form_name = 'Process ID not found in metadata', resolved[sid][1], '', ''
        else:
            continue
        status_text = '; '.join(
            f"{label}: {', '.join(sorted(st[sid]))}" for label, st in (('01', status1), ('04', status2))
            if st.get(sid))
        not_included.append({'sample_alias': sid,
                             'Sample ID': stats['sample_ids'].get(sid, 'Process ID not found in metadata'),
                             'scientificName': sample['scientificName'],
                             'level': sample['level'], 'reason': reason,
                             'candidate_name': name,
                             'request_form_name': forms[0][form_name][1] if form_name else '',
                             'queried_ena': queried,
                             'status_01_04': status_text, '_form_name': form_name})
    with open(not_included_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['sample_alias', 'Sample ID', 'scientificName', 'level', 'reason',
                                               'candidate_name', 'request_form_name', 'queried_ena',
                                               'status_01_04'],
                                extrasaction='ignore')
        writer.writeheader()
        writer.writerows(not_included)

    # Summary
    logger.info('=' * 70)
    logger.info('SUMMARY')
    logger.info('=' * 70)
    logger.info(f"Metadata rows: {stats['metadata_rows']} "
                f"({stats['outside_batch']} not in this batch - ignored)")
    logger.info('Taxid sources:')
    for source in ('01 ENA match (ID)', '04 ENA match (ID)', '04 ENA match (confirmed name)', 'ENA v2 lookup'):
        logger.info(f"  {source}: {source_stats.get(source, 0)}")
    if source_stats.get('conflicting sources'):
        logger.info(f"  samples where sources disagreed (see warnings): {source_stats['conflicting sources']}")
    reasons = Counter(r['reason'].split(';')[0] for r in not_included)
    logger.info(f"Checklist rows written: {len(rows)} -> {checklist_path}")
    logger.info(f"Not included: {len(not_included)} -> {not_included_path}")
    for reason, n in reasons.most_common():
        line = f"  {reason}: {n}"
        if reason.startswith('requested'):
            unique = {r['_form_name'] for r in not_included if r['reason'].split(';')[0] == reason}
            line += f" samples ({len(unique)} unique request-form names)"
        logger.info(line)
    if forms[0]:
        matched = {r['_form_name'] for r in not_included if r['_form_name']}
        unmatched = sorted(set(forms[0]) - matched)
        logger.info(f"Request-form names not matched to a pending batch sample: {len(unmatched)} "
                    f"of {len(forms[0])} (e.g. already have a taxid, edited on the form, or another batch)")
        for name in unmatched[:50]:
            logger.debug(name)
        if unmatched:
            logger.info(f"  first examples: {', '.join(unmatched[:10])}")
    logger.info(f"Reconciliation: {len(rows)} included + {len(not_included)} not included = "
                f"{len(rows) + len(not_included)} (batch total {len(batch)})"
                + ('' if len(rows) + len(not_included) == len(batch) else '  <-- MISMATCH'))
    logger.info(f"Mandatory fields filled with '{MISSING}':")
    for col in MANDATORY_COLUMNS:
        if col != 'project name':
            logger.info(f"  {col}: {stats['missing_fills'].get(col, 0)}")
    if stats['lifestage_unmapped']:
        logger.info(f"Lifestage values not on ENA's list ({sum(stats['lifestage_unmapped'].values())}) "
                    f"- written as '{MISSING}':")
        for value, n in stats['lifestage_unmapped'].most_common():
            logger.info(f"  '{value}': {n}")
    if stats['country_changes']:
        logger.info(f"Country values changed to ENA's list ({sum(stats['country_changes'].values())}):")
        for change, n in stats['country_changes'].most_common():
            logger.info(f"  {change}: {n}")
    if stats['country_invalid']:
        logger.info(f"Country values still not on ENA's list ({sum(stats['country_invalid'].values())}) "
                    f"- kept as recorded, please correct:")
        for value, n in stats['country_invalid'].most_common():
            logger.info(f"  '{value}': {n}")
    if stats['date_fixes']:
        logger.info(f"Collection dates unreadable or implausible ({len(stats['date_fixes'])}) - written as '{MISSING}':")
        for line in stats['date_fixes']:
            logger.info(f"  {line}")
    if stats['coord_fixes']:
        logger.info(f"Coordinates not usable ({len(stats['coord_fixes'])}) - written as '{MISSING}':")
        for line in stats['coord_fixes']:
            logger.info(f"  {line}")
    logger.info('Done.')


if __name__ == '__main__':
    main()
