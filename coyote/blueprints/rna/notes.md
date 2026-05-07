# RNA Fusion Filter Notes

## Context
- Database inspected: `coyote_dev_3`
- Sample checked: `25MD16916-fusion-fusions`
- Goal: understand why `min_spanning_pairs` filter can return zero rows even when visible rows should pass.

## Findings (from `coyote_dev_3`)
- `samples.filters` keys are correct:
  - `min_spanning_pairs`
  - `min_spanning_reads`
  - `fusionlists`
  - `fusion_effects`
  - `fusion_callers`
- `fusions.calls[]` support fields are mixed types:
  - `spanpairs`: mix of `int` and `str`
  - `spanreads`: mix of `int` and `str`
- In this sample, many non-zero support values are strings (for example `"spanpairs": "49"`).
- Numeric query behavior proves the mismatch:
  - `calls.$elemMatch.spanpairs >= 1` (numeric threshold) can return zero/incorrect results when values are stored as strings.

## Root Cause
- Query expects numeric comparison (`$gte`) on `calls.spanpairs` / `calls.spanreads`.
- Collection stores these fields with mixed numeric/string types.
- Mongo type comparison causes expected rows to be skipped.

## Required Schema Contract (recommended)

### `fusions` collection (`calls[]` items)
- `spanpairs`: integer (required for numeric filtering)
- `spanreads`: integer (required for numeric filtering)
- `caller`: lowercase string enum:
  - `arriba`, `fusioncatcher`, `starfusion`
- `effect`: keep one consistent standard.
  - Current data includes values like `in-frame` and `out-of-frame`.
  - If normalized filtering is preferred, add `effect_norm` with values like `inframe`, `outframe`, `other`.

### `samples.filters`
- `min_spanning_pairs`: integer, min `0`
- `min_spanning_reads`: integer, min `0`
- `fusion_callers`: array of lowercase strings
- `fusion_effects`: use one consistent standard (either hyphenated raw values or normalized values, not mixed)

## Action to Take (data/schema side)
- Normalize `fusions.calls[].spanpairs` and `fusions.calls[].spanreads` to integers.
- Standardize fusion effect values used by both documents and filter settings.
- Keep key names consistent:
  - query/view/filter code uses `spanpairs` and `spanreads` in `calls[]`.
