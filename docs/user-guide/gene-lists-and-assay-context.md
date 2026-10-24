# Gene lists and assay context

The assay, configuration, and selected gene lists determine which analyses and
findings are available during review. They serve different purposes and should not
be treated as interchangeable filters.

| Resource | Meaning during review | Daily reference |
| --- | --- | --- |
| Assay · ASP | The physical assay design, omics layer, and panel scope. | [Assay definitions](../administration/administration-guide.md#assays-asp) |
| Configuration · ASPC | Available analyses, review defaults, and reporting settings for the assay, diagnosis, and environment. | [Configuration settings](../administration/administration-guide.md#assay-configurations-aspc) |
| Gene list · ISGL | A versioned selection of genes eligible for a particular analysis and assay context. | [Gene-list administration](../administration/administration-guide.md#in-silico-gene-lists-isgl) |
| Diagnosis | A named clinical scope associated with an assay; its configuration is independent of another assay using the same name. | [Diagnoses](../administration/assay-diagnoses.md) |
| Assay group | A registered grouping of assays used by configuration and eligibility rules. | [Assay groups](../administration/assay-groups.md) |
| Clinical rules | Published reporting logic for the applicable assay, diagnosis, analyte, and language. | [Clinical reporting rules](../reference/clinical-reporting-rules.md) |

For administrative field names and defaults, see [ISGL fields](../administration/clinical-resource-fields.md#gene-list-isgl).

## Select gene scope for review

1. Confirm the sample's assay and diagnosis before changing its filters.
2. Select the intended analysis and, for SNVs where available, somatic or germline intent.
3. Check the selected gene lists and any ad-hoc gene selection. Eligible lists depend
   on the assay or assay group, list type, and configured scope.
4. Review the resulting findings alongside the other active thresholds and selections.
   A gene list restricts gene scope; it does not supply missing analysis evidence.

SNV and CNV gene-list selections are separate. Fusion-compatible lists can apply to
RNA fusions and DNA translocations through their respective configurations. Selecting
a list in one analysis does not imply that every analysis uses it. An eligible list
does not affect a query until it is selected.

## Configuration and sample changes

Changing review filters affects the sample's working view. Changing an ASP, ASPC, or
shared ISGL is an administrative operation with a wider scope and its own permissions.
The sample records its resolved configuration context; saved reports preserve their
reporting evidence rather than being regenerated from current configuration.

Each configuration captures exact assay and selectable gene-list revisions. Editing
those shared resources does not change an already assigned sample. To apply a newer
configuration, select **Review configuration update**, review the filter changes,
choose whether to retain compatible sample overrides, and provide a reason. A
concurrent sample edit or a changed active release requires another preview.

![Sample configuration resolution](../assets/diagrams/sample-configuration-resolution.svg)

Saving filters or applying a configuration increments the sample's operation version.
The audit event records the actor, previous and new settings, and configuration
references. Configuration application also records the supplied reason. A stale edit
is rejected without replacing the saved settings.

Gene selections resolve independently for each analysis and intent. Selected lists
form a union intersected with the assay's eligible genes, including WGS and WTS.
An empty overlap returns no findings. Unrestricted eligibility requires an explicit
assay policy and approval reference; sequencing breadth alone does not enable it.
Base configuration fallback must be enabled explicitly and stays within the sample's
environment. The requested diagnosis remains unchanged.

- [Filters and gene lists](application-guide.md#filters-and-gene-lists)
- [Missing analyses or results](sample-readiness-and-missing-results.md)
- [Planning a configuration change](../administration/planning-configuration-changes.md)
- [Analysis-specific filtering reference](../reference/assay-filtering.md)
