# Plotting And Chart Export

> **Info**
>
> Coyote3 uses React-native chart components for application plots. The
> plotting layer is centralized so dashboard, QC, reporting, and coverage
> views share the same behavior.
>

## Design

The frontend uses Recharts through Coyote3 wrappers in
`frontend/src/components/plots`.

- `ChartPanel` provides chart title, description, export controls, and a stable
  visual container.
- Chart-specific components own only the plot geometry, such as bar, pie, or
  line series.
- Export helpers live in `frontend/src/lib/chart-export.ts`.

## Export Behavior

Charts can export:

- PNG for presentations and operational screenshots.
- SVG for vector output.
- CSV for the underlying plotted rows.

> **Tip**
>
> Prefer CSV export for clinical review or audit discussions. PNG and SVG are
> visual snapshots; CSV preserves the data that produced the chart.
>

> **Caution**
>
> Browser-generated PNG export serializes the current SVG chart and draws it to
> a canvas. Browser security restrictions can block this if future chart
> components embed cross-origin images.
>

## Implementation Rules

- Do not call Recharts directly from new pages unless the page is defining a
  reusable plot component.
- Use theme tokens, not hard-coded chart colors.
- Every chart must define an empty state.
- Every chart with clinical or operational value should expose CSV export.
- Genome-track style views can use custom SVG when the layout is genomic rather
  than statistical, but they should still use the shared panel/export pattern
  where practical.
