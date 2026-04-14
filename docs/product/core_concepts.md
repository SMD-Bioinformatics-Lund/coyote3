# Core Concepts: The Coyote3 Worldview

To effectively use or develop for Coyote3, it is helpful to understand the underlying "Mental Model" of how clinical genomic data is organized within the platform. Coyote3 is not just a database; it is a **Clinical Workflow Engine**.

---

## 1. The Clinical Identity: Samples and Cases

In Coyote3, everything revolves around the **Sample**.

*   **A Sample** is a physical aliquot of DNA or RNA.
*   **A Case** is a diagnostic event. One Case might involve multiple Samples (e.g., a Tumor sample and a Germline/Normal control).

When you "ingest" data, you are telling Coyote3: *"Here is a sample, here is where it comes from, and here is its relationship to other biological material."*

---

## 2. The Instruction Set: ASP and ASPC

This is the most critical concept for understanding how Coyote3 "thinks."

### ASP (Assay Specific Panel)
Think of an **ASP** as a **Physical Definition**. It describes the wet-lab reality of a test:
*   Which genes were sequence?
*   What kit was used?
*   Is it DNA or RNA?

### ASPC (Assay Specific Configuration)
Think of an **ASPC** as a **Virtual Definition** or "Software Profile." It describes how the software should *behave* when looking at that ASP:
*   What are the default filter thresholds? (e.g., "Only show variants with >2% frequency")
*   What gene lists should be active?
*   What report template should be used?

**Why the split?** You might have one physical test (ASP) but use different software settings (ASPC) for a research project versus a clinical diagnostic run.

---

## 3. The Source of Truth: Data Contracts

Coyote3 uses **Strictly Typed Contracts**. This means the system has a rigid definition of exactly what a "Variant" or a "User" looks like.

*   If you send data that doesn't match the contract, the **API Engine** will reject it immediately.
*   This prevents "Data Rot"—where old or malformed data breaks the system months later.

---

## 4. The Permissions Model: Resource-Oriented

Coyote3 doesn't just have "Admins" and "Users." It uses a **Granular Permission System**.

*   Permissions look like `sample:edit:own` or `snv:manage:global`.
*   This allows a lab to give a technician permission to *edit their own samples* without giving them the ability to *delete the entire database*.

---

## 5. The Interpretation Lifecycle

Lastly, understand the state of a variant:

1.  **Ingestion**: Raw data arrives.
2.  **Triage**: A clinician looks at the findings.
3.  **Annotation**: The clinician adds comments, classifications (Tiers), and flags (Interesting! False Positive!).
4.  **Reporting**: A snapshot of all that work is "frozen" into a report. Even if the underlying database changes later, the report remains a permanent record of that moment in time.

---

### Still have questions?
Browse the [Workflow Chain Guide](workflow_dna_rna.md) for a deeper technical dive into these relationships.
