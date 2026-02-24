# Data Model and Collections

Coyote3 is easiest to understand if you follow how a case moves through the system. A case starts as a sample document, then DNA or RNA views pull molecular findings linked to that sample, annotation records add interpretation context, and report save locks the interpreted subset into report-linked snapshot records. This is the core lifecycle, and most debugging becomes straightforward once this flow is clear.

The `samples` collection is the operational anchor. It holds identity, assay context, profile/environment context, mutable filter state, and report history metadata. Live-versus-reported behavior is derived from sample report state, so when users ask why a case appears in one list and not another, the sample document is the first place to check.

The event collections hold source findings. `variants` powers SNV/indel workflows, while `cnvs` and `transloc` support structural sections that are enabled by assay configuration. These collections are not “report truth” on their own; they are source findings that can be interpreted differently over time.

Global interpretation knowledge lives in `annotation`. This is a shared collection with two document families: class/tier records and annotation text records. During case review, Coyote3 resolves matching annotation records by variant identity and assay scope. That is why a variant can look pre-tiered when opened in a new case under the same context.

Report-time truth is preserved in `reported_variants`. When a report is saved, the system writes report metadata on the sample and persists immutable snapshot rows for the reported variants. Those rows are intentionally not recalculated later when global annotation evolves. This separation between mutable live interpretation and immutable report snapshot is central to traceability.

Configuration is split across panel definitions, assay runtime behavior, and selectable gene lists. `assay_specific_panels` defines coverage scope and panel identity. `asp_configs` defines runtime behavior such as thresholds, enabled sections, and report structure. `insilico_genelists` provides curated selectable gene lists that modify case-level effective filtering. Together, these three collections explain why two assays can behave very differently even if their underlying findings look similar.

Access and governance use `users`, `roles`, `permissions`, and `schemas`. Users carry scope and overrides, roles carry baseline permission bundles, permissions define actionable capabilities, and schemas drive dynamic admin forms for managed configuration entities.

In practice, when something looks wrong, debug in this sequence: sample state, assay config and panel scope, source findings, annotation resolution, then report snapshots. This mirrors the actual runtime flow and avoids chasing downstream symptoms before confirming upstream context.
