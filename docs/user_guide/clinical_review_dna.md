# User Guide: DNA Clinical Review

The DNA Interpretation view is the main workspace for reviewing findings, assigning classifications, and building reports.

## Navigating the Review Workspace

The layout is organized for day-to-day review work:

*   **Vertical Navigation Sidebar**: On the left side, vertical tabs allow you to jump between different finding categories: SNV, CNV, Translocations, and the Summary report.
*   **Sample Context Card**: A persistent header showing patient details, assay configurations, and active gene list filters (ISGL).
*   **Integrated Documentation**: The "HELP" tab in the sidebar provides quick access to clinical manuals and standard operating procedures.

---

## 1. SNVs and Indels (Small Variants)

The primary variant table lists every finding passing the laboratory's quality filters.

### Key Table Features:
*   **Gene & HGVS**: Direct identification of the gene and specific mutation string. Gene names highlighted in red indicate high-priority "OncoKB" actionable genes.
*   **Consequence (CSQ)**: The selected transcript consequence terms from VEP. A variant can show more than one consequence term when the selected transcript carries a combined effect such as `missense_variant&splice_region_variant`.
*   **PopFreq %**: The frequency of the variant in public populations (gnomAD).
*   **GT (Genotype)**: Shows the Allelic Fraction (AF) and raw read depth (e.g., `12.5% (45 / 360)`).
*   **Quality Filter Badges**: Compact status badges summarize raw VCF filter output. Common examples are `PASS`, `GERM`, `HP`, `SB`, `LO`, `XLO`, `PON`, `FFPE`, `N`, `P`, and `LD`.

### Interpretation Actions:
Clinicians can perform the following actions directly on the table:
*   **Interesting Variant**: Flag a variant for further review or fellow clinician consultation.
*   **False Positive (FP)**: Flag artifacts or sequencing errors to remove them from the reporting pool.
*   **Blacklist**: Permantly flag a specific variant coordinate as a known technical artifact for that assay.
*   **IGV Viewing**: Clicking on the **Chr:Pos** badge will remotely load the genomic region in your local IGV (Interactive Genomics Viewer).

### Reading the filter badges

- `PASS` means the variant passed the primary quality gates.
- `GERM` represents `GERMLINE` or `GERMLINE_RISK` style flags.
- `HP`, `SB`, `LO`, `XLO`, `PON`, and `FFPE` are grouped warning or caution badges.
- `N`, `P`, and `LD` are grouped failure badges.
- The interface may collapse several raw pipeline-specific warning or failure tokens into the same short badge for readability.

---

## 2. Copy Number Variants (CNV)

The CNV section combines a profile plot with tabular data.

### Visual Profile
A high-resolution chromosome plot visualizing copy-number gain and loss across the genome.
*   **Interactive Rotation**: Use the toggle switch to rotate the profile 90 degrees for better orientation during multi-monitor review.
*   **External Links**: Buttons labeled "Open in Gens" allow you to open the sample in advanced CNV visualization tools for deeper breakpoint analysis.

### CNV Tabular Data
A detailed list of specific gain/loss events, including:
*   **Copy Number**: The calculated state (e.g., `Gain (3.2x)`).
*   **Affected Genes**: A list of all clinical genes residing within the CNV region.
*   **Artefact Probability**: A heat-mapped badge indicating whether similar events are common in the laboratory's background artifact frequentcy (AFRQ).

---

## 3. Structural Findings (Translocations)

Dedicated section for structural rearrangements and fusions identified at the DNA level. Each translocation includes detailed breakpoint coordinates and supporting read-count metrics.

---

## 4. Finalizing the Review

The **SUMMARY** section at the bottom of the page acts as your "Report Builder."
*   **Selected Findings**: Variants you have assigned a Tier (I-IV) or flagged as "Reportable" will automatically appear here.
*   **Clinical Summary**: A markdown-enabled text editor for drafting the overall diagnostic narrative.
*   **Report Generation**: Once the review is complete, use the "Preview Report" or "Generate Final Report" buttons to produce the clinical document.
