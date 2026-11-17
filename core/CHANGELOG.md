# Core changelog

## v4.0.0

- Allow scoped viewers to read sample workspace context without granting editing permissions.
- Add database-independent resource reads with strict typed filters, fresh permissions,
  paired assay/environment grants and authorization of related metadata queries.
- Own reusable manifest, metadata and retrieval models in core alongside clinical
  contracts. Preserve structural and clinical sample validation without a separate
  contracts distribution.
- Keep base model/validation installation lightweight; reporting and alignment/VCF
  capabilities use optional dependency extras within the same core distribution.
- Use typed `dna`/`rna` report identities and the shared `coyote3` renderer preset;
  reject old file-like identifiers and require renewed template-profile approval.
  Validate the full assay modality when compiling published template profiles.
- Move cell formatting into the document layer and renderer imports to module
  scope, removing the circular dependency without changing report presentation.
- Remove the implicit `ratio > 3` size bypass for ratio-based CNVs. High
  amplifications must pass the configured size limits, as in the production query;
  retain strict cutoff boundaries and explicit published admission rules.
- Resolve CNV genes from selected CNV lists, then panel coverage, then an
  unrestricted scope when neither is present. Preserve explicit empty selections
  across analysis, query previews and report eligibility.
- Express normal/control CNV exclusion as a visible, replaceable query rule, with
  the existing WGS inclusion default, typed `NORMAL` field and captured provenance.
- Verify that DNA translocation MANE selection matches each gene partner's own
  transcript; preserve fallback selection and separate RNA fusion handling.
- Separate administration by managed resource, clinical-rule authoring by scope,
  assignments and lifecycle, and DNA reports by evidence selection, snapshots and
  document sections. Preserve review transitions, clinical eligibility and rendered
  content; fingerprint every document-builder module for preview validation.
- Share assay-file, analysis-selection and sequencing-platform normalization across
  contracts, analysis views and reports while preserving validation and selection order.
- Apply one scope-matching implementation to SNV and structural finding query
  exceptions, preserving their typed criteria, modes and diagnostic ordering.
- Own reusable installation configuration compilation, reference-bundle provenance
  contracts and enabled host extension capabilities.

- Own durable ingestion job execution and manifest acknowledgement through
  explicit host ports, preserving fenced claims, transaction completion and retry recovery.
- Own the shared permission catalog and built-in role templates, with explicit
  server installation and no database access when loading packaged definitions.
- Package VEP consequence grouping and label policy independently of server-owned
  HGNC/VEP reference snapshots and their installation.
- Reject boolean and nonfinite CNV measurements before normalization; preserve
  caller event labels and valid rounding, and handle unusable copy-number values
  safely in analysis, exports and report projection.
- Match assay-configuration repository contracts to the implemented active-state
  filters and typed analysis rollups.
- Own portable clinical, contract and workflow regression tests, isolated synthetic
  ports, a fast smoke suite and complete-source branch coverage.
- Include the separate Ram Nanduri/SMD copyright and contributor notice in
  distributions and identify first-party source with GPL-3.0-only SPDX headers.
- Accept explicit public-reference availability settings instead of a backend
  configuration dictionary in anonymous catalog operations.
- Invalidate dashboard metrics through configured cache ports without inspecting
  an adapter or host runtime configuration.
- Distribute the framework-independent `coyote` namespace as `coyote-core`.
- Keep MongoDB codecs, provider identities and repositories in the server's
  separate `coyote_mongo` component.
- Expose the core version from its own installed distribution metadata.
- Preserve clinical operations, report inputs, rule evaluation and snapshots.
- License this package under GNU GPL version 3 only.
- Start the independent core at version 4.0.0 for the fourth-generation clinical library.
