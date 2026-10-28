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

Dashboard charts live in separate modules under `components/dashboard/`:
`SampleCompositionCharts`, `TierDistributionChart`, `GeneCoverageChart`,
`PanelAnalysisCapabilityChart` and `TopTieredGenesChart`. Knowledgebase charts
(`CancerGeneCensusChart` and `KnowledgebaseStatisticsCharts`) live under
`components/knowledgebase/`. Pages lazy-load the chart they use. Shared row types
and donut presentation settings belong to `components/plots/chart-data.ts` and
`chart-options.ts`; source-specific calculations stay with the corresponding chart.

## Export Behavior

Charts can export:

- PNG for presentations and operational screenshots.
- SVG for vector output.
- CSV for the underlying plotted rows.

> [!TIP]
>
> Prefer CSV export for clinical review or audit discussions. PNG and SVG are
> visual snapshots; CSV preserves the data that produced the chart.
>

> [!CAUTION]
>
> Browser-generated PNG export serializes the current SVG chart and draws it to
> a canvas. Browser security restrictions can block this if future chart
> components embed cross-origin images.
>

## Implementation Rules

- Do not call Recharts directly from new pages unless the page is defining a
  reusable plot component.
- Use theme tokens, not hard-coded chart colors.
- Recharts axes, grids, legends and default tooltips use shared styles in
  `frontend/src/styles/charts.css`. Preserve clinical series colors; use neutral
  foreground tokens for labels and values. Chart exports resolve displayed SVG
  styles and retain the active theme.
- Every chart must define an empty state.
- Every chart with clinical or operational value should expose CSV export.
- Genome-track style views can use custom SVG when the layout is genomic rather
  than statistical, but they should still use the shared panel/export pattern
  where practical.
