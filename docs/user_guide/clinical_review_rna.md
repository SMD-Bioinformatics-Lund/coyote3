# User Guide: RNA Clinical Review

The RNA Interpretation view is used for fusion review and expression analysis.

## Workspace Layout

The RNA workspace follows the same basic layout as the DNA review:

*   **Vertical Tab Navigation**: Quickly switch between Fusions, Classification, Expression, and Summary sections.
*   **RNA Sample Context**: Displays RNA-specific metadata, including fusion panel definitions and quality metrics.

---

## 1. Fusion Interpretation

The Fusion Table lists transcribed rearrangements passing the laboratory's bioinformatic pipeline.

### Table Features:
*   **Gene Pair (Gene 1 & Gene 2)**: The two partner genes involved in the fusion event.
*   **Spanning Pairs & Unique Reads**: Quantitative evidence supporting the fusion. High read counts typically indicate a high-confidence finding.
*   **Fusion Points**: Exact genomic coordinates for the fusion breakpoint.
*   **Tier Assignment**: Clinical significance categorization (Tiers I-IV).
*   **Effect & Description**: Functional predictions (e.g., "In-frame", "Out-of-frame") and detailed annotations about the fusion's known clinical relevance.

### Filtering and Triage:
Use the **Right Sidebar** to adjust fusion confidence thresholds. Variants flagged as Artifacts or False Positives will be visually dimmed to reduce noise during review.

---

## 2. Gene Expression Metrics

Quantitative expression data is presented to support fusion findings or identify expression-driven biomarkers.

*   **TPM (Transcripts Per Million)**: The normalized expression level for clinical genes of interest.
*   **Z-Score Visualization**: A visual bar showing how the sample's expression compares to a reference cohort.
    *   **Green Bar (Positive)**: Indicates overexpression (Up-regulation).
    *   **Red Bar (Negative)**: Indicates under-expression (Down-regulation).

---

## 3. Expression-Based Classification

For specific assays, Coyote3 runs machine-learning classifiers to predict clinical subtypes based on the overall expression profile.

*   **Classifier Scores**: A probabilistic score (0.00 to 1.00) for each predicted class.
*   **Model Versioning**: The specific classifier version used is displayed to ensure clinical auditability.

---

## 4. Summary and RNA Reporting

Like the DNA workflow, the Summary section allows you to compile your findings into a final diagnostic narrative.
*   Select reportable fusions and expression markers.
*   Preview the RNA diagnostic report.
*   Finalize and snapshot the report for the clinical record.
