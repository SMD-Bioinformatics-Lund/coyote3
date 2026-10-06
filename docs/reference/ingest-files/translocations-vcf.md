# DNA translocations: SnpEff-annotated VCF

Manifest key: `transloc`. Stored destination: `translocations`.

## Before submission

Provide breakend alleles and SnpEff `ANN` annotations. A generic structural-variant VCF is insufficient: symbolic alleles are skipped, and only records annotated with `gene_fusion` or `bidirectional_gene_fusion` are retained. Unlike small variants, translocation parsing does not resolve case/control roles from manifest IDs.

[Download the complete synthetic VCF](../../assets/examples/ingest/translocations-vcf.vcf), including header declarations and tab-separated records. All example identifiers and values are synthetic.
Ingest assigns `SAMPLE_ID` from the parent sample. Do not supply database IDs or review
state in pipeline files. The file must also satisfy the assay's required/expected file policy.

## Raw structure and fields

Illustrative annotation-bearing breakend record (real columns are tab-separated):

```text
#CHROM POS ID REF ALT QUAL FILTER INFO FORMAT SYNTHETIC-T
1 10001 bnd1 A A]2:20001] 60 PASS SOMATIC;SVTYPE=BND;ANN=A|gene_fusion|HIGH|GENE1&GENE2|ENSG000001&ENSG000002|transcript|ENST000001&ENST000002|protein_coding||c.?|p.? GT:PR:SR:UR 0/1:10,5:8,3:3
```

The ANN header must define the same order using SnpEff's ` | ` field-name
separators. For the excerpt this is `Allele | Annotation | Annotation_Impact |
Gene_Name | Gene_ID | Feature_Type | Feature_ID | Transcript_BioType | Rank |
HGVS.c | HGVS.p`. Header-declared extra fields remain possible.

| Key | Description | Mapping to `translocations` |
| --- | --- | --- |
| Standard VCF columns | Contig, position, alleles, source ID, quality | Same top-level fields; FILTER and FORMAT become lists |
| `INFO.SVTYPE` | Structural event type | Same nested key |
| `INFO.MATEID`, `INFO.EVENT` | Mate record and event identifiers | Same nested keys |
| `INFO.SVINSLEN`, `INFO.SVINSSEQ` | Inserted sequence length and sequence | Same nested keys |
| `INFO.SOMATIC` | Somatic flag | Boolean, default false |
| `INFO.SOMATICSCORE`, `INFO.JUNCTION_SOMATICSCORE` | Caller evidence scores | Optional integers |
| `INFO.BND_DEPTH`, `INFO.MATE_BND_DEPTH` | Breakend depths | Optional integers |
| `INFO.PANEL` or `INFO.set` | Panel labels | Normalized into `INFO.PANEL[]` |
| `ANN.Allele` | Annotated allele | `INFO.ANN[].Allele` |
| `ANN.Annotation` | Ampersand-separated effects | List; only records containing `gene_fusion` or `bidirectional_gene_fusion` are retained |
| `ANN.Annotation_Impact` | SnpEff impact | Same annotation key |
| `ANN.Gene_Name`, `ANN.Gene_ID` | Gene names and identifiers, possibly joined with `&` | Same annotation keys |
| `ANN.Feature_Type`, `ANN.Feature_ID` | Annotated feature class and identifiers | Same annotation keys |
| `ANN.Transcript_BioType`, `ANN.Rank` | Transcript type and rank | Same annotation keys |
| `ANN.HGVS.c`, `ANN.HGVS.p` | HGVS descriptions | Stored as `HGVSc`, `HGVSp` (dots removed from keys) |
| `ANN.cDNApos`, `ANN.cDNAlength`, `ANN.CDSpos`, `ANN.CDSlength`, `ANN.AApos`, `ANN.AAlength` | Optional positions and lengths | Optional integer fields with these storage names; they are not inferred from unrelated combined fields |
| `ANN.Distance` | Optional distance annotation | Text |
| `ANN.ERRORS`, `ANN.WARNINGS`, `ANN.INFO` | Annotation diagnostics | Preserved; combined key `ERRORS / WARNINGS / INFO` normalizes to `INFO` |
| Genotype `PR`, `SR` | Paired/split-read support | Text; tuple values become comma-separated strings; missing → empty text |
| Genotype `UR` | Unique-read evidence | Float or null |
| Sample column name | Genotype source | `GT[].sample`; translocation parser does not apply the SNV case/control role resolver |

`INFO.MANE_ANN` is not selected by the current file parser because its MANE map
is empty. Symbolic ALT values containing `<` are skipped. Do not submit a generic
unannotated SV VCF and assume every structural variant will become a translocation.

## Requirements and missing values

| Input | Requirement / omission behavior |
| --- | --- |
| Standard VCF identity and alleles | Required; no coordinate or allele default. Symbolic ALT records are skipped. |
| `INFO.ANN` and header order | Required to produce supported gene-fusion findings; nonqualifying annotations do not become stored translocations. |
| ANN `Allele`, `Gene_Name`, `Gene_ID`, `Feature_Type`, `Feature_ID` | Required in a retained annotation; no substitute gene or transcript IDs. |
| ANN `Annotation` | Must include a qualifying fusion term for retention. |
| Other listed ANN fields | Optional in the stored contract; missing fields remain absent/null rather than inferred. |
| `INFO.SOMATIC` | Missing normalizes to `false`; absence is not independent germline evidence. |
| Optional INFO event, insertion, score and depth fields | No measured default; missing values remain absent/null. |
| `INFO.PANEL` | Empty list when no panel/set values are supplied. |
| Genotype `PR`, `SR` | Missing becomes empty text, not zero support. |
| Genotype `UR` | Missing becomes null. |
| `ID`, `QUAL` | Missing ID becomes `.`; missing quality remains null. |

The stored annotation contract is not permission to omit the VCF structure that
the parser needs. Use the downloadable file as a syntax example and validate real
producer outputs in an isolated test deployment.

## Related contracts

- [Bundle preparation and file index](README.md)
- [Sample manifest](../sample-manifest.md)
- [Stored collection contracts](../mongodb-collections.md)
