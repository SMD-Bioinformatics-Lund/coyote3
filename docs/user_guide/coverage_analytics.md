# Coverage Analytics Guide

The Coverage Analytics suite allows clinicians to verify the diagnostic depth and technical quality of genomic sequencing for a specific sample. It ensures that critical regions (e.g., clinically actionable exons) have been sequenced with sufficient sensitivity.

## 1. Per-Base Coverage View

The Per-Base view provides a high-resolution graph of sequencing depth across the targeted genomic regions.

### Key Features
*   **Depth Thresholds**: Visual horizontal lines representing the minimum required depth (e.g., 50x, 100x, 500x).
*   **Zoom and Pan**: Interactive charts allow you to zoom into specific exons or focus on broad genomic blocks.
*   **Transcript Switcher**: Toggle between different genetic transcripts to ensure coverage on all relevant coding variants.

---

## 2. Low-Coverage Region Detection

Coyote3 automatically identifies "Gaps" or "Hotspots" where the sequencing depth falls below the laboratory-defined threshold.

### Navigating Gaps
*   **Gap Table**: A list of all regions that failed to meet the quality baseline, prioritized by gene importance and clinical tier.
*   **Exon Breakdown**: Detailed percentage of each exon covered at specific depth tiers (e.g., "% at 100x").
*   **Blacklist Management**: (Admins Only) Mark specific noisy or clinically irrelevant regions to be hidden from the default review view.

---

## 3. Blacklisted Regions

In some cases, specific genomic coordinates may consistently produce poor data or are known artifacts.

*   **View Blacklist**: Access a consolidated list of regions currently excluded from quality metrics.
*   **Impact on Reporting**: Blacklisted regions are clearly noted in the clinical report to ensure transparency regarding technical limitations.

---

## 4. Navigation & Workflow

1.  **From Interpretation**: While reviewing DNA findings, click the **Coverage** button in the sample header.
2.  **Verify Gaps**: Review the Gap Table to ensure no critical mutations were missed due to low depth.
3.  **Cross-Reference**: Use the **IGV Link** to visually inspect the raw alignment data (BAM) for any ambiguous regions.
