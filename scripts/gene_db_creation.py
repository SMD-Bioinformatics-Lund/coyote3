#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

import csv
from copy import deepcopy
from datetime import datetime


def load_file(path, delimiter="\t", skip_header_lines=0):
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=delimiter)
        lines = list(reader)

    header = lines[skip_header_lines]
    data = lines[skip_header_lines + 1 :]
    return header, data


# === Load HGNC main file (TSV, skip 1 metadata line) ===
main_header, main_data = load_file(
    "hgnc_complete_set.txt", delimiter="\t", skip_header_lines=1
)

# === Load extra file (CSV, no header skip) ===
extra_header, extra_data = load_file(
    "ensemble_biomark_clean_05052025.csv", delimiter=",", skip_header_lines=0
)

hgnc_header_mapping = {
    "hgnc_id": {"name": "hgnc_id", "type": str, "separator": None},
    "symbol": {"name": "hgnc_symbol", "type": str, "separator": None},
    "name": {"name": "gene_name", "type": str, "separator": None},
    "status": {"name": "status", "type": str, "separator": None},
    "location": {"name": "locus", "type": str, "separator": None},
    "location_sortable": {
        "name": "locus_sortable",
        "type": str,
        "separator": None,
    },
    "alias_symbol": {"name": "alias_symbol", "type": str, "separator": "|"},
    "alias_name": {"name": "alias_name", "type": str, "separator": "|"},
    "prev_symbol": {"name": "prev_symbol", "type": str, "separator": "|"},
    "prev_name": {"name": "prev_name", "type": str, "separator": "|"},
    "date_approved_reserved": {
        "name": "date_approved_reserved",
        "type": datetime,
        "separator": None,
    },
    "date_symbol_changed": {
        "name": "date_symbol_changed",
        "type": datetime,
        "separator": None,
    },
    "date_name_changed": {
        "name": "date_name_changed",
        "type": datetime,
        "separator": None,
    },
    "date_modified": {
        "name": "date_modified",
        "type": datetime,
        "separator": None,
    },
    "entrez_id": {"name": "entrez_id", "type": int, "separator": None},
    "ensembl_gene_id": {
        "name": "ensembl_gene_id",
        "type": str,
        "separator": None,
    },
    "refseq_accession": {
        "name": "refseq_accession",
        "type": str,
        "separator": "|",
    },
    "cosmic": {"name": "cosmic", "type": str, "separator": "|"},
    "omim_id": {"name": "omim_id", "type": int, "separator": "|"},
    "pseudogene.org": {
        "name": "pseudogene_org",
        "type": str,
        "separator": "|",
    },
    "imgt": {"name": "imgt", "type": str, "separator": None},
    "lncrnadb": {"name": "lncrnadb", "type": str, "separator": None},
    "lncipedia": {"name": "lncipedia", "type": str, "separator": None},
    "mane_select_ensembl": {
        "name": "ensembl_mane_select",
        "type": str,
        "separator": None,
    },
    "mane_select_refseq": {
        "name": "refseq_mane_select",
        "type": str,
        "separator": None,
    },
}


ensembl_header_mapping = {
    "Chromosome/scaffold name": {
        "name": "chromosome",
        "type": str,
        "separator": None,
    },
    "Gene start (bp)": {"name": "start", "type": int, "separator": None},
    "Gene end (bp)": {"name": "end", "type": int, "separator": None},
    "Strand": {"name": "strand", "type": int, "separator": None},
    "Transcript start (bp)": {
        "name": "transcript_start",
        "type": int,
        "separator": None,
    },
    "Transcript end (bp)": {
        "name": "transcript_end",
        "type": int,
        "separator": None,
    },
    "Transcript length (including UTRs and CDS)": {
        "name": "transcript_length",
        "type": int,
        "separator": None,
    },
    "Gene type": {"name": "gene_type", "type": str, "separator": None},
    "HGNC ID": {"name": "hgnc_id", "type": str, "separator": None},
    "HGNC symbol": {"name": "hgnc_symbol", "type": str, "separator": None},
    "RefSeq match transcript (MANE Select)": {
        "name": "refseq_mane_select",
        "type": str,
        "separator": None,
    },
    "RefSeq match transcript (MANE Plus Clinical)": {
        "name": "refseq_mane_plus_clinical",
        "type": str,
        "separator": "|",
    },
    "Gene description": {
        "name": "gene_description",
        "type": str,
        "separator": None,
    },
    "Ensembl Canonical": {
        "name": "ensembl_canonical",
        "type": bool,
        "separator": None,
    },
    "Transcription start site (TSS)": {
        "name": "transcription_start_site",
        "type": int,
        "separator": None,
    },
    "Gene % GC content": {
        "name": "gene_gc_content",
        "type": float,
        "separator": None,
    },
}

# === Map headers to new names ===
main_header_formatted = [hgnc_header_mapping[h]["name"] for h in main_header]
main_header_format_dict = {
    hgnc_header_mapping[h]["name"]: {
        "type": hgnc_header_mapping[h]["type"],
        "separator": hgnc_header_mapping[h]["separator"],
    }
    for h in main_header
}
extra_header_formatted = [
    ensembl_header_mapping[h]["name"] for h in extra_header
]
extra_header_format_dict = {
    ensembl_header_mapping[h]["name"]: {
        "type": ensembl_header_mapping[h]["type"],
        "separator": ensembl_header_mapping[h]["separator"],
    }
    for h in extra_header
}


# === Create a dictionary for each row in the main data ===
def format_value(value, data_type, separator=None):
    """
    Format a value based on the specified data type and separator.

    Args:
        value (str): The value to be formatted.
        data_type (type): The target data type for the value.
        separator (str, optional): The separator to split the value if it's a list.

    Returns:
        The formatted value or None if the value is invalid or empty.
    """
    if separator and value:
        return [data_type(v.strip()) for v in value.split(separator)]
    elif separator and not value:
        return []
    elif not separator and not value:
        return None
    elif value and data_type == datetime:
        return datetime.strptime(value.strip(), "%d/%m/%Y")
    else:
        return data_type(value) if value else None


# Create a dictionary for each row in the main data
main_data_formatted = []
for md in main_data:
    md_formatted = {}
    for index, elem in enumerate(main_header_formatted):
        md_formatted[main_header_formatted[index]] = format_value(
            md[index],
            main_header_format_dict[main_header_formatted[index]]["type"],
            main_header_format_dict[main_header_formatted[index]]["separator"],
        )
    main_data_formatted.append(md_formatted)


# Main Data Sample: {'hgnc_id': 'HGNC:5', 'hgnc_symbol': 'A1BG', 'gene_name': 'alpha-1-B glycoprotein', 'status': 'Approved', 'locus': '19q13.43', 'locus_sortable': '19q13.43', 'alias_symbol': '', 'alias_name': '', 'prev_symbol': '', 'prev_name': '',
# 'date_approved_reserved': '30/06/1989', 'date_symbol_changed': '', 'date_name_changed': '', 'date_modified': '20/01/2023', 'entrez_id': '1', 'ensembl_gene_id': 'ENSG00000121410', 'refseq_accession': 'NM_130786', 'cosmic': '', 'omim_id': '138670',
# 'pseudogene_org': '', 'imgt': '', 'lncrnadb': '', 'lncipedia': '', 'ensembl_mane_select': 'ENST00000263100.8', 'refseq_mane_select': 'NM_130786.4'}

# === Create a dictionary for each row in the extra data ===
extra_data_dicts = {}
for ed in extra_data:
    hgnc_id = ed[extra_header_formatted.index("hgnc_id")]
    if hgnc_id not in extra_data_dicts:
        extra_data_dicts[hgnc_id] = []

    ed_formatted = {}
    for index, elem in enumerate(extra_header_formatted):
        ed_formatted[extra_header_formatted[index]] = format_value(
            ed[index],
            extra_header_format_dict[extra_header_formatted[index]]["type"],
            extra_header_format_dict[extra_header_formatted[index]][
                "separator"
            ],
        )

    extra_data_dicts[hgnc_id].append(ed_formatted)

# print(extra_data_dicts)
# 'HGNC:55675': [{'chromosome': '1', 'start': 41241772, 'end': 41338644, 'strand': 1, 'transcript_start': 41241772, 'transcript_end': 41338644, 'transcript_length': 4437, 'gene_type': 'lncRNA', 'hgnc_id': 'HGNC:55675', 'hgnc_symbol': 'SCMH1-DT', 'refseq_mane_select': None, 'refseq_mane_plus_clinical': [],
# 'gene_description': 'SCMH1 divergent transcript [Source:HGNC Symbol;Acc:HGNC:55675]', 'ensembl_canonical': True, 'transcription_start_site': 41241772, 'gene_gc_content': 45.37}],
# 'HGNC:52528': [{'chromosome': '1', 'start': 212467563, 'end': 212556085, 'strand': 1, 'transcript_start': 212467563, 'transcript_end': 212556085, 'transcript_length': 1151, 'gene_type': 'lncRNA', 'hgnc_id': 'HGNC:52528', 'hgnc_symbol': 'LINC01740', 'refseq_mane_select': None, 'refseq_mane_plus_clinical': [], 'gene_description': 'long intergenic non-protein coding RNA 1740 [Source:HGNC Symbol;Acc:HGNC:52528]', 'ensembl_canonical': True, 'transcription_start_site': 212467563, 'gene_gc_content': 45.42}]}


# TODO: Add a function to merge the two dictionaries
merged_dict = {}
for md in main_data_formatted:
    md_merged = deepcopy(md)
    hgnc_id = md["hgnc_id"]
    if hgnc_id in extra_data_dicts:
        ed_list = extra_data_dicts[hgnc_id]

        # Fixed values
        start = ed_list[0]["start"]
        end = ed_list[0]["end"]
        gene_gc_content = ed_list[0]["gene_gc_content"]
        gene_description = ed_list[0]["gene_description"]
        ensembl_canonical = ed_list[0]["ensembl_canonical"]

        # List values
        chromosome = []
        gene_type = []
        refseq_mane_plus_clinical = []
        addtional_transcript_info = {}

        for ed in ed_list:
            transcript_start = ed["transcript_start"]
            transcript_end = ed["transcript_end"]
            transcript_length = ed["transcript_length"]
            transcript_start_site = ed["transcription_start_site"]
            for ed_key, ed_value in ed.items():
                if ed_key == "chromosome":
                    chromosome.append(ed_value)
                elif ed_key == "gene_type":
                    gene_type.append(ed_value)
                elif ed_key == "refseq_mane_plus_clinical":
                    refseq_mane_plus_clinical.extend(ed_value)
                elif ed_key == "ensembl_canonical" and not ensembl_canonical:
                    ensembl_canonical = ed_value
                elif ed_key == "refseq_mane_select" and ed_value:
                    addtional_transcript_info[ed_value] = {
                        "start": transcript_start,
                        "end": transcript_end,
                        "length": transcript_length,
                        "start_site": transcript_start_site,
                    }
                elif ed_key == "refseq_mane_plus_clinical" and ed_value:
                    addtional_transcript_info[ed_value] = {
                        "start": transcript_start,
                        "end": transcript_end,
                        "length": transcript_length,
                        "start_site": transcript_start_site,
                    }

        # Remove duplicates
        chromosome = list(set(chromosome))
        gene_type = list(set(gene_type))
        refseq_mane_plus_clinical = list(set(refseq_mane_plus_clinical))
        # Remove empty values
        chromosome = [c for c in chromosome if c]
        gene_type = [g for g in gene_type if g]
        refseq_mane_plus_clinical = [r for r in refseq_mane_plus_clinical if r]

        if len(chromosome) == 1:
            chromosome = chromosome[0]
            other_chromosome = None
        elif len(chromosome) > 1 and "X" in chromosome and "Y" in chromosome:
            chromosome = "X"
            other_chromosome = "Y"

        md_merged["chromosome"] = chromosome
        md_merged["other_chromosome"] = other_chromosome
        md_merged["start"] = start
        md_merged["end"] = end
        md_merged["gene_gc_content"] = gene_gc_content
        md_merged["gene_description"] = gene_description.split("[")[0]
        md_merged["ensembl_canonical"] = ensembl_canonical
        md_merged["gene_type"] = gene_type
        md_merged["refseq_mane_plus_clinical"] = refseq_mane_plus_clinical
        md_merged["addtional_transcript_info"] = addtional_transcript_info

    merged_dict[hgnc_id] = md_merged


print("Merged dictionaries created")
print(merged_dict["HGNC:5"])

# write this merged dictionary to a json file for mongoDB import
import json
import os
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# MongoDB connection details
MONGO_URI = "mongodb://172.17.0.1:27017/"  # Replace with your MongoDB URI
MONGO_DB = "coyote_dev_3"
MONGO_COLLECTION = "hgnc_genes"
# Connect to MongoDB
try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]
    print("MongoDB connection successful")
except ConnectionFailure as e:
    print(f"MongoDB connection failed: {e}")
    exit(1)

# Create a directory for the output files
output_dir = "output"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
# Write the merged dictionary to a JSON file
output_file = os.path.join(output_dir, "merged_dict.json")
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(merged_dict, f, indent=4, default=str)
print(f"Merged dictionary written to {output_file}")
# Insert the merged dictionary into MongoDB
for hgnc_id, data in merged_dict.items():
    # Convert datetime objects to ISO format for MongoDB
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()

    data["_id"] = hgnc_id  # Use hgnc_id as the unique identifier

    # Insert the document into the collection
    # collection.insert_one(data)
