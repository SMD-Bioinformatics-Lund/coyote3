# RNA fusions: caller evidence JSON

Manifest key: `fusion_files`. Stored destination: `fusions`.

## Before submission

Use a root array. Every fusion must have a nonempty `calls` array with exactly one `selected: 1`. The caller must resolve through the center's configured fusion-caller vocabulary. Alternative calls may omit `selected`; they normalize to zero. Missing required breakpoints or support fields must not be replaced with invented measurements.

[Download the complete synthetic JSON](../../assets/examples/ingest/fusions.json). All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

```json
[
  {
    "gene1": "BCR",
    "gene2": "ABL1",
    "genes": "BCR-ABL1",
    "calls": [
      {
        "selected": 1,
        "caller": "arriba",
        "spanpairs": 20,
        "spanreads": 42,
        "longestanchor": 30,
        "breakpoint1": "22:23632600",
        "breakpoint2": "9:133589000",
        "effect": "in-frame",
        "desc": "synthetic_example"
      }
    ]
  }
]
```

| Key | Description and storage |
| --- | --- |
| `gene1`, `gene2` | Required fusion-partner names, stored at the root |
| `genes` | Required combined producer label, for example `BCR-ABL1` |
| `calls` | Nonempty array of independent caller observations |
| `calls[].caller` | Calling tool name, not the annotator version |
| `calls[].breakpoint1`, `calls[].breakpoint2` | Breakpoint strings retained as provided |
| `calls[].spanpairs` | Spanning-pair count, integer |
| `calls[].spanreads` | Spanning-read count, integer |
| `calls[].longestanchor` | Anchor length; integer or string accepted |
| `calls[].selected` | Exactly one call must be 1; omitted values become 0 |
| `calls[].effect` | Caller-authored frame/region description; omitted → empty text |
| `calls[].desc` | Caller evidence tags as text; omitted → empty text |
| `calls[].commonreads` | Common-read count; omitted → 0 |

## Caller evidence and review behavior

- Every fusion must contain exactly one call with `selected: 1`. Alternative
  calls may omit `selected`; ingest stores those values as `0`. The selected
  state identifies the caller observation displayed, classified, and reported.
- `calls[].effect` is caller-authored fusion frame or breakpoint-region context.
  The exact normalized value `in-frame` is presented as in-frame; every other
  non-empty value, including `out-of-frame` and `UTR/CDS(truncated)`, is
  presented as out-of-frame. It is not a DNA VEP `Consequence` value.
- `calls[].desc` is a comma-delimited, caller-controlled evidence vocabulary.
  Values such as `oncogene`, `cancer`, `reciprocal`, and caller-specific codes
  are retained verbatim. Coyote3 does not discard unknown future tags. The UI
  distinguishes curated/cancer-reference tags, cautionary context, and
  artifact-associated tags using the historical FusionCatcher vocabulary, but
  those visual groups are review aids rather than clinical classifications.
- Fusion description colors are driven by
  `api/config/center/clinical_vocabulary.toml`. Important cancer/reference
  terms are green, artifact or normal-tissue terms are red, contextual terms
  are gray, and unknown future caller terms remain visible with the neutral
  style.
- All caller alternatives remain in the same `fusions.calls` array. They are not
  written to `anno_vep`, because they are independent caller observations rather
  than alternate VEP transcript consequences. A reviewer may change the selected
  call on the fusion detail page; that operation clears the previous selection
  and marks exactly one call as selected.

Fusion eligibility and fusion presentation are intentionally separate. The
query admits a fusion when one individual call satisfies all configured caller,
effect, evidence, and read-support predicates. The table and report then present
the call marked `selected`. This preserves alternative caller observations
without allowing support from one call and effect from another to satisfy a
single filter expression.

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
