# Future work

This page records proposed development. It does not describe released capabilities
or commit to a delivery date. Implementation requires reviewed contracts, migration
plans and clinical workflow validation.

## Shared findings with separate somatic and germline interpretation

**Status: proposed; not implemented as a complete workflow.**

Current somatic SNV queries can return germline variants that satisfy their selection
criteria. Germline intent has configuration and query support, but the dedicated
germline pathway is not yet fully implemented. The current behavior and limitations
are described in [SNV query intent](../reference/assay-filtering.md#intent-specific-snv-review).

### Proposed model

Keep observations together by finding type and support separate interpretation
contexts. Reuse table components with clearly identified review views instead of
duplicating observations into somatic and germline collections.

| Concept | Responsibility | Proposed representation |
| --- | --- | --- |
| Finding observation | Preserve what an analysis detected in a specimen. | Stable observation identity with specimen, analysis, genotype, caller and evidence provenance. Separate specimens and analysis runs remain distinguishable. |
| Origin assessment | Record the evidence-supported assessment of origin. | Somatic, germline, uncertain or not assessed, with assessment status, evidence, author and history. Final terminology requires contract review, including mosaic and conflicting evidence. |
| Interpretation context | Record the clinical question and assessment framework. | Separate somatic and germline interpretations referencing the same observation when relevant. |

Origin belongs to the patient/specimen context, not to a globally shared variant
identity. A pipeline flag, allele frequency or inclusion in a somatic query must not
automatically become a confirmed origin assessment. Preserve source assertions
separately from reviewed conclusions, including disagreements.

A finding assessed as germline may also be relevant to tumor interpretation. It can
appear in both authorized review views without duplicating its observation or
equating the two interpretations.

### Review interface and clinical decisions

Provide a shared **Small variants** workspace with explicit review contexts, origin
assessment labels and evidence details. Each context may have its own filters,
columns and actions. An optional **All findings** view must respect server-side
permissions and the displayed filter scope. Counts must distinguish unique findings
from overlapping view membership.

Keep these decisions independently attributable to their interpretation context:

- Classification framework and result; somatic tiers must not be reused as germline
  pathogenicity classifications.
- Review status, reviewer, timestamps and change reasons.
- Context-specific comments and conclusions, distinguished from shared evidence.
- Report eligibility, inclusion decisions and wording.

Changing a filter, view or origin assessment must not silently reclassify a finding,
complete another workflow's review or add it to a report. The germline view should
be presented as a complete workflow only after its full interpretation and reporting
path has been implemented and validated.

### Applicability to other data types

| Data type | Proposed treatment |
| --- | --- |
| SNVs and indels | Shared observations with explicit origin assessments and separate clinical interpretations. |
| CNVs | Apply the same separation while retaining assay-specific evidence and the distinction between tumor copy-number measurements and constitutional deletion/duplication assessment. |
| DNA structural variants and translocations | Share observations across relevant contexts, with specimen evidence supporting origin assessment. |
| RNA fusions | Retain RNA evidence and link supporting DNA observations where available. An RNA fusion call alone must not establish germline origin. |
| HRD, MSI and TMB | Retain assay-result, specimen and method context; do not impose a universal somatic/germline classification. |
| Coverage and QC | Organize by specimen, assay, method and quality criteria. Variant origin is not the organizing concept. |
| PGX | Design around the required genotype/diplotype and pharmacogenomic interpretation model rather than relying on an origin label. |

### Implementation and release requirements

1. Review existing identity, classification, annotation, query, report and access
   contracts. Define which evidence is shared and which decisions belong to a context.
2. Introduce versioned origin assessments and context-specific interpretations with
   explicit provenance. Preserve unknown values; do not infer origin during migration
   solely from legacy tab names, query intent or caller flags.
3. Enforce access and editing permissions in APIs and exports. Hiding a view is not
   an authorization boundary. Define applicable consent and disclosure controls before
   enabling additional workflows at a center.
4. Add review views without changing existing selection behavior incidentally.
   Document any intentional query changes and validate them against representative
   synthetic cases before activation.
5. Snapshot the relevant interpretation, origin assessment and rule versions in new
   reports. Preserve historical reports and annotations without retrospective rewriting.
6. Validate overlapping view membership, conflicting evidence, missing controls,
   unassessed findings, independent classifications, authorization, exports and
   concurrent review. Test migration repeatability and recovery on isolated data.

### Design references

GA4GH VA-Spec distinguishes variant representations from statements, evidence and
study results, with provenance attached to those records. Consult the
[GA4GH Variant Annotation product page](https://www.ga4gh.org/product/variant-annotation/)
and the official [VA-Spec source repository](https://github.com/ga4gh/va-spec),
which includes documentation sources under `docs/source`. These references inform
the proposed design; they do not establish Coyote3 conformance or prescribe its
database layout. Implementation should select and record an
appropriate specification release.
