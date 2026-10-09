# HGNC gene reference installation

`scripts/gene_db_creation.py` joins a reviewed HGNC TSV file and an
Ensembl BioMart CSV export by HGNC ID. It validates the resulting documents against
the application's `HgncGenesDoc` contract and writes a review artifact. Database
writes require `--apply`; conversion alone does not connect to MongoDB.

For a first installation, `install_center.sh --setup-center` already installs the
bundled HGNC snapshot into an empty collection. This standalone command prepares
and installs a separately reviewed gene reference from source files. It does not
download data or refresh references automatically.

> [!IMPORTANT]
> Use HGNC and BioMart exports reviewed together for the intended assembly and
> release. Every supplied HGNC gene must have complete enrichment satisfying the
> current contract. A full upstream export can include genes without the required
> coordinates or identifiers; these are validation errors, not silently skipped rows.
> Prepare a reviewed input subset when needed and retain an inventory of exclusions.

## Prepare the source files

HGNC uses tab-separated columns with the header on the first line. An export with
one metadata line requires `--hgnc-skip-lines 1`. BioMart uses comma-separated
columns and a first-line header. Both files use UTF-8. Column names are case-sensitive;
duplicate headers and inconsistent row widths are rejected. Unmapped columns are
ignored. No missing numeric value is replaced with zero.

### HGNC columns

| Source column | Stored field | Format and requirement |
| --- | --- | --- |
| `hgnc_id` | `hgnc_id`, `_id` for new genes | Unique, nonblank HGNC identifier; join key |
| `symbol` | `hgnc_symbol` | Gene symbol matching BioMart |
| `name` | `gene_name` | Gene name |
| `status` | `status` | Source status; no automatic status filtering |
| `location`, `location_sortable` | `locus`, `locus_sortable` | Source strings |
| `entrez_id` | `entrez_id` | Required integer |
| `ensembl_gene_id` | `ensembl_gene_id` | Source identifier |
| `mane_select_ensembl`, `mane_select_refseq` | `ensembl_mane_select`, `refseq_mane_select` | Source transcript strings, including versions; blank remains blank |
| `alias_symbol`, `alias_name`, `prev_symbol`, `prev_name` | Same names | Optional pipe-separated string lists; omitted or blank means empty list |
| `refseq_accession`, `cosmic` | Same names | Optional pipe-separated string lists |
| `omim_id` | `omim_id` | Optional pipe-separated integer list |
| `pseudogene.org` | `pseudogene_org` | Optional pipe-separated string list |
| `date_approved_reserved`, `date_symbol_changed`, `date_name_changed`, `date_modified` | Same names | Optional `YYYY-MM-DD` or `DD/MM/YYYY`; blank means null |
| `imgt`, `lncrnadb`, `lncipedia` | Same names | Optional strings; omitted means null |

Columns not marked optional are required by the current collection contract.
Source strings are preserved without inventing absent identifiers.

### BioMart columns

| Source column | Meaning and validation |
| --- | --- |
| `HGNC ID`, `HGNC symbol` | Match the supplied HGNC gene and symbol |
| `Chromosome/scaffold name` | One chromosome per gene, or the X/Y pair; X is the primary locus and Y is recorded as `other_chromosome` |
| `Gene start (bp)`, `Gene end (bp)` | Positive, ordered genomic bounds; consistent across primary-locus rows |
| `Gene % GC content` | Numeric percentage from 0 to 100; consistent across primary-locus rows |
| `Gene description` | Consistent source description; trailing bracketed attribution is removed from display text |
| `Gene type` | Nonblank type; distinct values form `gene_type` |
| `Ensembl Canonical` | Explicit `1`, `0`, `true` or `false`; gene flag is true if any primary-locus row is canonical |
| `RefSeq match transcript (MANE Select)` | Optional transcript identifier, including version |
| `RefSeq match transcript (MANE Plus Clinical)` | Optional pipe-separated identifiers; every supplied transcript is retained |
| `Transcript start (bp)`, `Transcript end (bp)` | Required positive, ordered bounds for each supplied MANE transcript |
| `Transcript length (including UTRs and CDS)` | Required positive integer for each supplied MANE transcript |
| `Transcription start site (TSS)` | Required positive coordinate for each supplied MANE transcript |
| `Strand` | Optional integer parsed from the source; not stored in the current gene contract |

The gene-level coordinates, transcript metadata and MANE lists use the primary
locus. Conflicting metadata for the same transcript is rejected. The existing
collection field is spelled `addtional_transcript_info`; the importer retains that
contract. Missing Ensembl MANE Plus Clinical identifiers are not inferred from
RefSeq identifiers. Gene reference installation does not change transcript-selection
precedence or reannotate existing findings.

## Validate and review

Run from the repository root with the application's Python dependencies installed:

```bash
.venv/bin/python scripts/gene_db_creation.py \
  --hgnc /srv/coyote3/reference/hgnc.tsv \
  --biomart /srv/coyote3/reference/biomart.csv \
  --release center-reviewed-release \
  --assembly GRCh38 \
  --output /srv/coyote3/reference/genes-review.json
```

The output contains MongoDB Extended JSON gene records and provenance: the supplied
release, assembly and SHA-256 hashes of both inputs. Review the gene count, scope,
coordinates and transcript metadata. Validation stops on the first invalid record;
correct the input and rerun before applying. Output files must not already exist.

## Apply the reviewed input

Pause other gene-reference writers and use maintenance credentials with write access
to the configured knowledgebase database. Keep the reviewed inputs unchanged:

```bash
.venv/bin/python scripts/gene_db_creation.py \
  --hgnc /srv/coyote3/reference/hgnc.tsv \
  --biomart /srv/coyote3/reference/biomart.csv \
  --release center-reviewed-release \
  --assembly GRCh38 \
  --output /srv/coyote3/reference/genes-applied.json \
  --env-file "$COYOTE_ENV_FILE" \
  --apply \
  --backup /srv/coyote3/reference/genes-before.bson
```

> [!WARNING]
> `--apply` replaces complete records for the supplied HGNC IDs. Genes absent from
> the input remain unchanged, so this is a scoped import, not a full snapshot
> replacement. Existing MongoDB IDs are preserved. Back up and review before using
> a different assembly; existing sample annotations are not converted.

The command revalidates the inputs, writes the review artifact, backs up affected
records to a new owner-only BSON file, and checks those records have not changed
before committing replacements and publication activity in one transaction. A
replica set is required. Empty targets produce an empty backup file. Failed writes
do not make the earlier review artifact evidence of successful installation; check
the exit status and `applied_genes` output. No indexes or external knowledgebases
are installed by this command.

## Parameters

| Parameter | Required/default | Purpose |
| --- | --- | --- |
| `--hgnc FILE` | Required | HGNC TSV input |
| `--biomart FILE` | Required | Reviewed BioMart CSV input |
| `--hgnc-skip-lines N` | Default `0` | Metadata lines before the HGNC header |
| `--release NAME` | Required | Operator-supplied reference release label |
| `--assembly NAME` | Required | Reviewed assembly; recorded as provenance, not inferred or converted |
| `--output FILE` | Required, new file | Review artifact; parent directory must exist |
| `--env-file FILE` | Optional | Deployment environment; exported process variables take precedence |
| `--apply` | Default off | Enable database installation after validation |
| `--backup FILE` | Required with `--apply`, new file | BSON backup of affected existing genes; parent directory must exist |

Database installation uses the standard endpoint configuration and the
application-owned `hgnc_collection` mapping (`hgnc_genes`). All four logical endpoint
selections must be configured so database separation can be validated; only the
knowledgebase endpoint is connected. See the
[environment reference](../deployment/configuration-reference.md) and
[installation operations](../deployment/installation-operations.md).
