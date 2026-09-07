# Script Maintenance TODO

- Deprecate the sample-ID/BAM-service lookup used by IGV after upstream producers
  populate `samples.case.bam`, `samples.case.bai`, and the corresponding control
  fields. Prepare a reviewed, dry-run-first backfill for older sample documents;
  do not guess paths or modify existing explicit references. Verify all centers
  can access the declared files from IGV before removing the fallback, including
  the sample-ID link in the variants table and the BAM-service lookup endpoint.
  Keep the fallback supported until that migration and deprecation are approved.
