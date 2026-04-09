# Template Components

Use the shared macro library for repeated UI fragments instead of copying badge,
chip, and button markup between templates.

## Macro files

- `coyote/templates/macros/badges.html`
- `coyote/templates/macros/actions.html`

## Available macros

### `tier_badge(tier, href=None, label=None, extra_classes='')`

Render a consistent colored tier pill.

```jinja
{{ tier_badge(fus.classification.class) }}
{{ tier_badge(var.classification.class, href=tier_href, label=var.classification.class) }}
```

### `status_badge(text, tone='gray', extra_classes='')`

Render a reusable status pill for labels such as `FP`, `Interesting`, or
`Irrelevant`.

```jinja
{{ status_badge('FP', tone='orange') }}
{{ status_badge('Interesting', tone='teal') }}
```

### `meta_chip(label, value, tone='gray', extra_classes='')`

Render a compact metadata chip for key-value sample or variant facts.

```jinja
{{ meta_chip('HGVSc', csq.HGVSc) }}
{{ meta_chip('hash', variant.simple_id_hash) }}
```

### `link_button(label, href, tone='neutral', extra_classes='')`

Render a standardized action link button.

```jinja
{{ link_button('Edit Sample', url_for('home_bp.edit_sample', sample_id=sample_id)) }}
{{ link_button('Analysis', url_for('dna_bp.list_dna_findings', sample_id=sample_id)) }}
```

## Current adopters

The macro library is already used by:

- `coyote/blueprints/dna/templates/list_dna_findings.html`
- `coyote/blueprints/rna/templates/list_fusions.html`
- `coyote/blueprints/dna/templates/tiered_variant_info.html`

## Rule of thumb

If a template introduces another repeated badge, chip, or action-button pattern,
add or extend a macro first and then consume it from the template. That keeps
style changes centralized and makes future UI cleanup much cheaper.
