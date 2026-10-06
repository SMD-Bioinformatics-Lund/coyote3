# Gene lists and assay context

The assay, configuration, and selected gene lists determine which analyses and
findings are available during review. They serve different purposes and should not
be treated as interchangeable filters.

| Resource | Meaning during review | Daily reference |
| --- | --- | --- |
| Assay · ASP | The physical assay design, omics layer, and panel scope. | [Assay definitions](../administration/administration-guide.md#assays-asp) |
| Configuration · ASPC | Available analyses, review defaults, and reporting settings for the assay, subpanel, and environment. | [Configuration settings](../administration/administration-guide.md#assay-configurations-aspc) |
| Gene list · ISGL | A versioned selection of genes eligible for a particular analysis and assay context. | [Gene-list administration](../administration/administration-guide.md#in-silico-gene-lists-isgl) |
| Subpanel | A named clinical scope associated with an assay; its configuration is independent of another assay using the same name. | [Subpanels](../administration/assay-subpanels.md) |
| Assay group | A registered grouping of assays used by configuration and eligibility rules. | [Assay groups](../administration/assay-groups.md) |
| Clinical rules | Published reporting logic for the applicable assay, subpanel, analyte, and language. | [Clinical reporting rules](../reference/clinical-reporting-rules.md) |

For administrative field names and defaults, see [ISGL fields](../administration/clinical-resource-fields.md#gene-list-isgl).

## Select gene scope for review

1. Confirm the sample's assay and subpanel before changing its filters.
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

- [Filters and gene lists](application-guide.md#filters-and-gene-lists)
- [Missing analyses or results](sample-readiness-and-missing-results.md)
- [Planning a configuration change](../administration/planning-configuration-changes.md)
- [Analysis-specific filtering reference](../reference/assay-filtering.md)
