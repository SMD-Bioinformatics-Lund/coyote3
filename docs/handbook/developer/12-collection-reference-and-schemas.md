# Collection Reference and Document Schemas

This reference explains what each important collection is for, how it is used at runtime, and how it relates to other collections during real workflows.

The central object in Coyote3 is always the sample. Everything else either describes how that sample should be interpreted, provides findings attached to that sample, or preserves report-time interpretation outcomes for that sample. If you keep this model in mind, the collection landscape is coherent rather than fragmented.

Samples define the operational case state. They carry assay, profile, filter state, report pointers, and comment context. Any user-facing behavior around live worklists, done worklists, or case-specific settings starts here.

Molecular findings are stored separately by finding type. SNV/indel records are retrieved from `variants`, copy-number records from `cnvs`, and translocation records from `transloc`. These are raw interpretation inputs from the application perspective, not final historical truth.

Interpretation knowledge is shared through `annotation`, where class/tier entries and free-text interpretation entries coexist. The application resolves these records by variant identity and context, so the same molecular event can pick different interpretation records across assay/subpanel scope.

Historical reporting is handled by `reported_variants`. At report save time, Coyote3 writes immutable snapshot rows that tie sample, report, variant identity, and report-time tier together. This gives stable history views even if annotation changes later.

Runtime behavior is driven by assay configuration collections. `assay_specific_panels` defines panel-level biological scope and covered genes. `asp_configs` defines what sections are shown, how filtering behaves, and how reporting is rendered. `insilico_genelists` provides curated, selectable gene sets that influence effective filtering at case level.

Governance is modeled through `users`, `roles`, `permissions`, and `schemas`. These collections are the reason route access, admin forms, and managed configuration editing behave consistently across the system.

From a development perspective, the practical mapping is simple: sample gives context, event collections provide findings, annotation provides interpretation, assay collections control behavior, and reported snapshot rows preserve audit-safe history. Any new feature should respect this separation instead of mixing concerns across collections.
