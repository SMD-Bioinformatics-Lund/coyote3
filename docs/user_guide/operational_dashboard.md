# Operational Dashboard

The Operational Dashboard is the primary landing page for Coyote3, providing a high-level overview of laboratory throughput, clinical quality signals, and active workloads. It is accessible at the `/dashboard` route.

![Coyote3 operational dashboard](../assets/screenshots/dashboard.png)

!!! info "Dashboard purpose"

    The dashboard is optimized for fast orientation. It uses aggregated backend data and compact charts so reviewers can see workload, review quality, and resource health without opening every sample table.

## Operational Overview

At the top of the dashboard, metric cards summarize the current state of the laboratory:

*   **Total Samples**: The cumulative count of all clinical samples ingested into the platform.
*   **Analysed Samples**: Samples that have been reviewed and finalized by a clinician.
*   **Pending Samples**: The current active backlog requiring clinical attention.
*   **Analysed Rate**: A percentage indicating the laboratory's efficiency in clearing the sample queue.
*   **Available Findings**: Current variant, CNV, fusion, translocation, and coverage availability when those domains are enabled.

## Analytical Charts

The dashboard uses reusable React chart components with export support where appropriate. Charts are placed inside the same glass-card system as the rest of the application.

### 1. Sample Progress
A donut chart visualizing the ratio of Analysed vs. Pending samples. This allows at-a-glance monitoring of the current workload status.

### 2. Variant Composition
Displays the distribution of findings across different analysis domains, including small variants, CNVs, translocations, RNA fusions, and other enabled modules. This helps clinicians understand the complexity of the current workload.

### 3. Tier Distribution
A bar chart showing the categorization of variants that have been included in clinical reports (Tiers I through IV). This provides a snapshot of the clinical significance of findings across the platform.

### 4. Quality Snapshot
A radial chart monitoring three critical quality markers:
*   **Analysed Rate**: Progress toward completion.
*   **Blacklist Rate**: Percentage of variants identified as known technical artifacts.
*   **False Positive (FP) Rate**: Percentage of findings manually flagged as false results by clinicians.

## My Assay Workload

This section is personalized to your assigned assays. It shows a breakdown of progress for each assay group (e.g., Solid Tumors, Myeloid, WGS).

*   **Actionable Navigation**: Clicking on any bar in this chart will take you directly to the filtered Sample List for that specific assay group, allowing for rapid transition from oversight to action.

## Platform Capacity and Metadata

For administrators and senior lead clinicians, additional resource panels show the growth of the system knowledgebase, including the number of active assay panels (ASP), configurations (ASPC), and gene lists (ISGL) currently powering review logic.

## Visual Design

Dashboard panels use the standard Coyote3 glass-card surface:

| UI element | Behavior |
| --- | --- |
| Metric cards | Compact values with short-count formatting, consistent borders, and clinical color accents. |
| Charts | Plotting components receive normalized backend aggregates and avoid loading full sample or variant tables. |
| Recent samples | Uses the same bordered table conventions as other application tables. |
| Empty states | Explain why a chart is empty instead of showing a blank plotting area. |
