# File formats, field requirements and defaults

Coyote3 accepts several kinds of files with different owners and purposes. A
pipeline input, an API request and a stored database document may describe the
same sample but have different fields. Use the reference for the boundary being
submitted; a database export is not automatically a valid ingest manifest.

## Reading a field table

| Term | Meaning | Example |
| --- | --- | --- |
| Required | Supply the field in this format. There is no omission default. | `classifier_version` in classification JSON. |
| Conditional | Required when another field or selected workflow makes it applicable. | Control identity for a paired sample. |
| Optional | May be omitted; the reference states the resulting value or behavior. | Omitted `TMB.unit` becomes `mut/Mb`. |
| Derived or service-owned | Set by Coyote3, not invented by the producer. | Analysis `SAMPLE_ID` comes from the parent sample. |
| Default | Value assigned when the field is omitted at this boundary. | Missing CNV `nprobes` becomes `0`; that is not evidence that probes were counted. |
| Example | An illustration of valid syntax, not an approved center value. | Synthetic sample IDs and assay names. |
| Nullable | An explicit `null` is accepted where stated. | Unknown region coverage. Optional does not automatically mean nullable. |

A missing key, `null`, empty text, an empty array and numeric zero are different
values. Do not interchange them unless the specific contract documents that
normalization. A measured zero must not be used to represent an unavailable test.
Defaults at the raw parser, stored schema and application form can differ. The
reference names the relevant boundary; workflow validation still applies after
basic field validation.

## Formats used by the application

| Format | How to recognize it | Used for | Editing rules |
| --- | --- | --- | --- |
| Environment text | One `NAME=value` per line | Private deployment settings | [Environment syntax and precedence](../configuration/environment-file.md). |
| TOML | `[section]` headings and `key = value` | Center vocabulary, query policy, contact information and application mappings | Quoted text, typed numbers/booleans, arrays in brackets; consult each [file reference](../configuration/README.md). |
| YAML | Indented mappings with `key: value` | Sample manifests, flag metadata and Compose services | Spaces define nesting; do not use tabs. Their schemas are unrelated despite sharing syntax. |
| JSON object | `{ "key": "value" }` | Individual resources and structured measurement inputs | Double-quoted keys/text, no comments or trailing commas; use `null`, `true` and `false`. |
| JSON array | `[ {...}, {...} ]` | Collections of rows, such as fusion evidence | Follow the per-file root shape; an object and array are not interchangeable. |
| NDJSON | One complete JSON object per line | Bootstrap catalogs and selected import tools | Not a JSON array; do not submit it to a JSON upload endpoint unless explicitly supported. |
| VCF | Metadata/header lines followed by tab-delimited records | SNV and translocation evidence | Each supported pipeline contract defines annotations and genotype fields; a generic VCF is not sufficient. |
| TSV/text | Header plus delimited rows | Selected knowledgebase imports and migration backfills | Use the exact importer columns, encoding and missing-value rules. |
| Binary/archive | Image, alignment, compressed dataset or ZIP bundle | Visual review, indexed alignments and transport | Renaming an extension does not convert the file. Use the corresponding consumer's accepted format. |

Raw analysis JSON is read as UTF-8. Empty files and malformed JSON fail with the
filename and, for syntax errors, line/column information. Valid JSON syntax alone
does not establish correct measurements or clinical compatibility.

## Choose the contract

- [All configuration and resource references](../configuration/README.md): select by owner and purpose.
- [Sample manifest](sample-manifest.md): identity, clinical scope and file declarations.
- [Analysis input files](ingest-files/README.md): one reference per supported measurement format.
- [Collection import requests](../api/collection-imports.md): transport options and document validation.
- [Database contracts](mongodb-collections.md): persisted fields; not raw pipeline schemas.
- [Reporting rules](clinical-reporting-rules.md): governed clinical logic and publication requirements.
- [Knowledgebase updates](../operations/knowledgebase-updates.md): source-specific datasets and publication.
- [Migration from v2](../migration_from_v2/README.md) and [v3](../migration_from_v3/README.md): legacy inputs, inventories and missing-data backfills.

Before a submission, check the selected assay, file shape, required fields, units,
identifiers and process-visible paths. Use the workflow's validation or dry-run
facility where available. An ingest submission writes data; it is not a harmless
format checker. Use synthetic records in an isolated test deployment for end-to-end
verification.
