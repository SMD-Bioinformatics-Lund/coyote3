# Clinical Interpretation Workflow Guide

This guide provides a step-by-step walkthrough of the clinical analysis process in Coyote3—from the initial sample triage to variant classification and reporting.

---

## 1. Entering the Analysis Workspace

Every clinical analysis starts at the **Sample List**.

![Sample List](../assets/screenshots/samples_list.png)

1.  **Locate Your Sample**: Use the search bar or filters to find the target patient or case.
2.  **Access the View**: Click on the **Sample ID** (blue link).
    *   **DNA Samples**: Opens the SNV/Indel and CNV interpretation view.
    *   **RNA Samples**: Opens the Fusion and Expression analysis view.

---

## 2. Navigating the Interpretation Interface

The analysis page is divided into three functional zones:
*   **Central Workspace**: Displays clinical metadata, active gene panels, and interactive variant tables (SNV, CNV, Translocation).
*   **Global Navigation Sidebar (Left)**: Vertical links to jump between sections (SNV, CNV, BIOMARKER, SUMMARY) or access the **Coverage Analytics** and **Report Preview**.
*   **Action & Filter Sidebar (Right)**: The command center for fine-tuning data visualization and performing batch operations.

---

## 3. Mastering Analytical Filters

The **Right Sidebar** contains real-time filters that allow you to narrow down thousands of sequencing artifacts to a handful of clinically significant variants.

### SNV Filters
*   **Min Depth & Alt Count**: Set minimum sequencing sensitivity (e.g., Depth ≥ 500x).
*   **Frequency Control (VAF)**: Adjust the minimum and maximum Allelic Fraction (e.g., 0.05 to 1.0).
*   **Population Frequency (PopFreq)**: Filter out common polymorphisms using GnomAD frequency thresholds (e.g., ≤ 0.01).
*   **Consequence & Gene Lists**: Use the dropdowns to focus only on specific variant types (e.g., Missense, Nonsense) or specific virtual panels (ISGL).

### CNV Filters
*   **Ratio Thresholds**: Adjust Gain/Loss ratios to detect large genomic events.
*   **Size Filtering**: Limit the view to large chromosomal shifts or focal gene-level events.

---

## 4. Variant Classification (Tiering)

Coyote3 supports a standardized classification workflow based on ACMG/AMP and Comper guidelines.

### Individual Tiering
1.  Click the **View** button next to any variant to see the detailed evidence page.
2.  Click the **Tier** button in the variant header to open the classification modal.
3.  Assign the **Tier (I-IV)** and select the specific evidence criteria (e.g., PM1, BA1).
4.  **Save**: The classification persists across all clinical views and propagates to the final report.

### Bulk Operations (Batch Actions)
For high-efficiency triage, use the **Bulk Action Bar**:
1.  Select multiple variants using the checkboxes in the SNV table.
2.  In the **Right Sidebar**, under "Modify Variants," select the desired status (e.g., **False Positive** or **Irrelevant**).
3.  Click **Apply**: All selected variants are updated simultaneously, drastically reducing review time.

---

## 5. Clinical Dialogue and Reporting

### Adding Comments
*   **Variant Narrative**: Click the **Chat Bubble** icon on any variant to record professional narratives or internal laboratory notes.
*   **Privacy**: You can "Hide" developer or technical feedback from the clinical interface to maintain a clean workspace.

### Final Summary
At the bottom of the page, the **SUMMARY** section allows you to draft the overall clinical interpretation.
*   This text uses a Markdown editor for rich-text formatting.
*   The summary enters the final PDF report exactly as rendered here.

---

## 6. Visual Evidence Tools

*   **CNV Profile Plot**: View the interactive chromosome profile. Use the **90° Rotate** toggle in the CNV header for closer inspection of focal events.
*   **IGV (Integrative Genomics Viewer)**: Click any **Chr:Pos** link to trigger the web-based IGV. This loads the raw alignment data (BAM) for per-base evidence verification.
*   **Gens Integration**: Deep links are available to open cases in the Gens visualize tool for advanced copy-number and BAF assessment.
