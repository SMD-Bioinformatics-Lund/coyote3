# Flow Diagrams

This page provides operational flow diagrams for the most used workflows in Coyote3.

## 1. Sample Flow

```text
Samples Worklist (/samples)
  -> Open Sample Settings (/samples/<sample_id>/edit)
  -> Apply ISGL / ad-hoc genes
  -> Open DNA or RNA workspace
  -> Review and classify
  -> Preview report
  -> Save report
  -> Sample moves from Live to Done/Reported
```

## 2. DNA Flow

```text
/samples
  -> /dna/sample/<sample_id>
  -> load sample + ASPC + schema
  -> compute effective genes from:
       ASP (Assay Specific Panel)
       + ISGL (In Silico Gene List)
       + ad-hoc genes
  -> review SNV/CNV/Translocation
  -> classify/comment/flag
  -> preview report
  -> save report (/dna/sample/<sample_id>/report/save)
```

## 3. RNA Flow

```text
/samples
  -> /rna/sample/<sample_id>K=
  -> load sample + RNA config
  -> apply caller/effect thresholds
  -> review fusions
  -> classify / mark FP / comment
  -> preview report
  -> generate PDF report
```

## 4. Admin Flow (Operational)

```text
/admin
  -> choose domain:
       Users / Roles / Permissions / ASP / ASPC / ISGL
  -> create or edit configuration
  -> validate schema-required fields
  -> save
  -> validate using smoke sample
  -> verify intended access and runtime behavior
```

## 5. End-to-End Flow (Case to Report)

```text
Intake -> Samples -> Settings (ISGL/ad-hoc) -> DNA/RNA interpretation
-> Classification/comments -> Preview -> Final report save/export
-> Report history retrieval
```

## Related chapters

- [Navigation and Page Map](./03-navigation-and-pages.md)
- [DNA Workflow](./04-dna-workflow.md)
- [RNA Workflow](./05-rna-workflow.md)
- [Admin and Governance](./07-admin-and-governance.md)
- [Complete Click Paths](./11-complete-click-paths.md)
