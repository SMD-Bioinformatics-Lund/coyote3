# Reference Guide

This section contains the shared, canonical reference for Coyote3. It defines
the terms, contracts, and rules used by the clinical interface, administration
workflows, deployment procedures, and software services.

Use a user or administration guide for step-by-step workflows. Use these pages
when a specific field, configuration key, collection, rule, or supported input
format must be understood precisely.

| Subject | Reference |
| --- | --- |
| ASP, ASPC, ISGL, and sample relationships | [Core Concepts](../product/core_concepts.md) |
| DNA and RNA processing model | [DNA and RNA Workflow](../product/workflow_dna_rna.md) |
| Query filters and exceptions | [Query and Filter Strategy](../product/aspc_driven_query_strategy.md) |
| Report rule grammar and rendered text | [Clinical Reporting Rules](../product/clinical_reporting_rules.md) |
| Saved reports and finding snapshots | [Reporting and Snapshots](../product/reporting_workflow_and_variant_snapshots.md) |
| Clinical data flow and storage | [Clinical Data and Reporting Flow](../architecture/clinical_data_and_reporting_flow.md) |
| Ingest manifest fields | [Sample YAML Manifest](../api/sample_yaml.md) |
| Ingested data-file formats | [Sample Input Files](../api/sample_input_files.md) |
| MongoDB collection fields and validation | [Collection Contracts](../api/collection_contracts.md) |
| Terms used in the clinical interface | [Clinical Vocabulary](../operations/clinical_vocabulary.md) |
| Supported external knowledgebases | [OncoKB](../product/oncokb_integration.md) and [ClinPGx](../product/clinpgx_integration.md) |

The collection-contract reference is generated from the Pydantic schemas. Do
not edit it manually; update the schema and regenerate the document.
