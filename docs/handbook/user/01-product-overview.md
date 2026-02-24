# Product Overview

## What Coyote3 is

Coyote3 is a workflow platform for molecular diagnostics interpretation and reporting.

It centralizes:

- sample intake and operational visibility
- DNA/RNA interpretation workflows
- assay-specific filtering and gene-list logic
- report generation and retrieval
- controlled access and governance

## Primary user groups

- clinical analysts reviewing DNA/RNA findings
- molecular diagnosticians and bioinformatics users managing interpretation logic
- laboratory users tracking sample/report status
- administrators managing users, permissions, assays, schemas, and gene lists

## Core modules

- **Samples** (`/samples`): live and reported case worklists
- **DNA** (`/dna`): SNV/CNV/translocation interpretation and report workflow
- **RNA** (`/rna`): fusion interpretation and report workflow
- **Dashboard** (`/dashboard`): operational monitoring
- **Search** (`/search/tiered_variants`): cross-sample interpretation history
- **Admin** (`/admin`): governance and runtime configuration
- **Public** (`/public`): public-facing informational routes

## Key concepts

- **Live sample**: case in active interpretation cycle
- **Reported sample**: case with one or more saved reports
- **ISGL**: curated in-silico gene lists associated with assay context
- **Ad-hoc genes**: case-specific gene constraints stored in sample filters
- **Effective genes**: final gene set applied during filtering and interpretation
- **ASP / ASPC**: panel definitions (`assay_specific_panels`) and assay runtime/report configurations (`asp_configs`)

## Security posture

- authenticated sessions via login subsystem
- route-level permission enforcement
- sample-level access enforcement
- audit logging for critical user actions
