# ASPC-Driven Query Strategy

`asp_configs` (ASPC) is the runtime strategy contract for variant retrieval and review behavior.
Each center controls query behavior through ASPC `filters` (base thresholds/guards) plus resource-specific Mongo query JSON, without code changes.

## Runtime relationship

1. `samples.assay` + `samples.profile` resolves one ASPC (`aspc_id = <assay>:<environment>`).
2. ASPC `filters` provide default threshold/guard values.
3. Sample-level filters persist user changes and override ASPC defaults for that sample.
4. Query resolution uses merged filters together with resource-specific query JSON for SNV, CNV, fusion, and translocation retrieval.

## ASP, ASPC, ISGL interplay

- `assay_specific_panels` (ASP): assay metadata and covered-gene universe.
- `asp_configs` (ASPC): environment-specific filter and reporting strategy.
- `insilico_genelists` (ISGL): optional center/user-curated gene scopes.

Effective genes are derived from:

- ASP covered genes
- selected ISGL lists
- adhoc sample genes

Those effective genes flow into SNV/CNV/fusion query scopes.

### SNV base groups

The SNV resolver uses two base groups before the resource query JSON is applied:

- `generic_germline`: germline flags and hotspot escape branches
- `generic_somatic`: case/control/population-frequency/consequence branches

Center-specific assay groups can use either base group or combine both:

- `hematology`, `myeloid`, `tumwgs`, and `unknown` resolve both base groups under a single top-level OR
- `generic_germline` resolves only the germline-style branches
- `generic_somatic` resolves only the somatic-style branches

This keeps the core SNV behavior stable while making the shared base logic explicit and reusable.

Assay scope is explicit in ASPC:

- `assay_groups`: one or more assay groups
- `assays`: one or more assays inside those groups

The admin UI keeps the scope controls simple:

- selecting a group reveals the assays in that group
- multiple groups can be selected together
- assays can also be selected directly
- query values are stored as raw Mongo JSON in the profile
- ASPC `filters` provide the center-specific values referenced by that JSON
- reporting content is configured in ASPC and is not part of the query profile

## ASPC query model

SNV base threshold keys stay in `filters`:

- `min_alt_reads`, `min_depth`, `min_freq`, `max_freq`, `max_control_freq`, `max_popfreq`
- `vep_consequences`

Resource-specific query JSON is configured directly in ASPC.

Each domain accepts:
- `$or` for additional allow branches
- `$and` for additional required clauses
- any other Mongo operator/field condition at root

Mongo operators are passed through as provided by ASPC JSON.

## Example ASPC filter block (DNA)

```json
{
  "min_freq": 0.03,
  "max_freq": 1.0,
  "max_control_freq": 0.05,
  "max_popfreq": 0.01,
  "min_depth": 100,
  "min_alt_reads": 5,
  "min_cnv_size": 100,
  "max_cnv_size": 1000000,
  "cnv_loss_cutoff": -0.3,
  "cnv_gain_cutoff": 0.3
}
```

## Example ASPC query block (DNA SNV)

```json
{
  "snv": {
    "$or": [
      {"INFO.MYELOID_GERMLINE": 1},
      {
        "$and": [
          {"genes": {"$in": ["FLT3"]}},
          {"$or": [{"INFO.SVTYPE": {"$exists": "true"}}, {"ALT": ".*"}]}
        ]
      }
    ],
    "$nor": [
      {"FILTER": {"$in": ["FAIL"]}}
    ]
  }
}
```

## Example ASPC filter block (RNA)

```json
{
  "min_spanning_reads": 2,
  "min_spanning_pairs": 5,
  "fusion_callers": ["arriba", "starfusion"],
  "fusion_effects": ["in-frame"]
}
```

## Admin UI behavior

ASPC admin forms are generated from backend contracts.
`filters` is edited in structured sections and the query JSON is edited directly in one text field.

The admin UI keeps the editing surface simple:

- assay groups reveal the assays they contain
- multiple groups can be selected together
- assays can also be selected directly
- query JSON is edited as raw Mongo syntax in one text field
- ASPC `filters` provide the center-specific values referenced by that query JSON
- reporting content is configured in ASPC and is not part of the query JSON

All query payloads are validated by backend Pydantic models before persistence.

## Default ISGL behavior in ASPC

ASPC controls assay+environment defaults for ISGL selection:

- `filters.genelists` defines the default SNV genelists for all samples resolved by that ASPC (`assay_name + environment`).
- `filters.cnv_genelists` defines default CNV genelists for the same scope.
- `filters.fusion_genelists` defines default fusion genelists for the same scope.

If these list fields are left empty, no default list is auto-applied, and users select lists manually per sample in Sample Settings.

### Auto-select by diagnosis/subpanel

`use_diagnosis_genelist` enables diagnosis-driven list matching.

In the ASPC UI this should be presented as:

- `Auto select diagnosis/sub panel genelists`

When enabled, the system auto-selects ISGLs where ISGL `diagnosis` matches the sample diagnosis/subpanel context.
When disabled, only explicit selections apply.
