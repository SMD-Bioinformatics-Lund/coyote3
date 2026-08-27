# Complete user manual

This manual explains the Coyote3 clinical and operational interface. It is
written for clinical reviewers, laboratory staff, managers, and administrators.
Developer and deployment procedures are in the
[complete developer manual](../developer/complete_developer_manual.md).

## What Coyote3 does

Coyote3 brings assay configuration, analysis results, clinical review,
comments, and reports into one application. It does not run a sequencing
pipeline. It receives pipeline output that has passed ingest validation and
presents the analyses enabled for that sample.

| Term | Meaning |
| --- | --- |
| Sample | One submitted DNA or RNA analysis case. |
| ASP | The assay definition: platform, assay family, covered genes, and expected files. |
| ASPC | The assay configuration used for a sample: enabled analyses, filters, and report sections. |
| ISGL | An in-silico gene list that can restrict an analysis to a selected gene scope. |
| Finding | A small variant, CNV, fusion, translocation, biomarker, or other result under review. |
| Annotation | A classification or text attached to a defined finding identity. |
| Report snapshot | The findings, filters, configuration, and text saved with a report. |

## Sign in and public pages

The login page shows the authentication methods enabled by the deployment.
Local and LDAP sign-in may both be available. If a provider is shown but its
service cannot be reached, Coyote3 reports the provider error without changing
the other sign-in method.

The public catalog, assay matrix, gene-list pages, About page, and Contact page
can be available without a session. Access to sample and administration pages
always requires a session and the relevant permissions.

| Login action | Result |
| --- | --- |
| Sign in | Creates an application session and opens the requested protected page. |
| Forgot password | Sends or records a password-reset request according to the center's mail configuration. |
| Sign out | Ends the current browser session. |
| Open public catalog | Opens public assay information without signing in. |

## Main navigation

The top bar contains the application identity, DNA and RNA sample menus, theme
control, notifications, and account menu. The side bar provides routes for the
current user. Routes that require a permission or a disabled application module
are not offered as usable actions.

| Area | Use |
| --- | --- |
| Dashboard | Review workload, sample composition, finding counts, and assay configuration summaries. |
| Samples | Find live or reported samples and enter the analysis workspace. |
| Variant search | Search classifications and annotation text across reported findings. |
| Gene cohort | Review reported findings, prevalence, and recurrence for one gene. |
| Reports | Find reports that have already been saved. Reports are created inside a sample. |
| Catalog | Review public assay, panel, gene-list, and gene coverage information. |
| Notifications | Read messages addressed to the current user. |
| Admin | Manage resources allowed by the current user's permissions. |

The side bar can be collapsed. On narrow screens, tables and controls adapt to
the available width; wide tables become horizontally scrollable only when their
columns can no longer remain readable.

## Dashboard

The dashboard is a summary, not a live query console. The API prepares a cached
snapshot in the background so opening the page does not need to recalculate all
metrics. An authorized user can request an immediate refresh from the page.

| Section | What it answers |
| --- | --- |
| Operational snapshot | How many visible samples are analysed and awaiting review? |
| Review workload | Which assays have pending samples? |
| Recent samples | What are the five most recently added visible samples? |
| Sample composition | How are samples distributed by status, omics, scope, environment, pairing, and pipeline? |
| Variant review | How many findings, classifications, false positives, blacklisted findings, and reported findings exist? |
| Panel gene coverage | How many covered and germline genes are assigned to active targeted panels? |
| Panel analysis capability | Which analyses are enabled and reportable across active panel configurations? |
| Clinical configuration | How many ASPs, ASPCs, ISGLs, users, and roles are available? |

Dashboard counts are limited by the current user's access scope. A zero can
mean either that no matching records exist or that none are visible to the
current account.

## Find samples

Open **Samples** to view live and reported work. The date control limits the
result set by the sample added date. Search is applied by the backend to all
matching samples, not only to the current page.

| Control | Meaning |
| --- | --- |
| Production / all profiles | Limit the list to production or include every permitted environment. |
| DNA / RNA menu | Limit samples by omics layer, assay family, and assay group. Counts follow the current accessible sample set. |
| Date added | Select today, a recent period, all dates, or an exact date range. |
| Rows per page | Set the page size. Remaining results stay available through pagination. |
| Search | Match the supported sample and case identity fields across the full result set. |
| Live samples | Samples still in analysis or awaiting a report. |
| Reported samples | Samples with saved report history. |

### Sample table

| Column | Meaning |
| --- | --- |
| Sample | Application sample name and link to the workspace. |
| Case / control | Pipeline case and optional control identifiers. |
| Clarity fields | LIMS identifiers supplied by the manifest. |
| Environment | Production, validation, testing, or development scope. |
| ASP and subpanel | Assay and requested in-silico scope. |
| Analysis | Current sample readiness. |
| Report | Reported or unreported state. |
| Counts | Available analysis records. Green badges indicate loaded data; failed or partial data uses an error state. |
| Added | Time since ingest, displayed in the configured local time zone. |
| Latest report | Most recent saved report date on the reported-samples view. |

The sample export contains visible identity and assay fields, loaded analysis
counts, biomarker values where available, and blank columns where a supported
value is absent.

## Sample workspace

The sample header identifies the sample, ASP, environment, and readiness. It
may also show purity, FFPE state, or biomarker summaries. The overview records
the ASPC ID and version attached to the sample.

### Analysis layouts

The analysis layout is stored in the user's `ui_settings.analysis_layout`.

| Layout | Behavior |
| --- | --- |
| Classic | Shows enabled finding sections on one page. Each section has its own filter button. |
| Modern | Shows one enabled analysis at a time in tabs. |

The first-use banner disappears after the user has tried the Modern layout.
Changing the layout does not change filters, classifications, or report data.

### Why a tab may be absent

An analysis is shown only when it is valid for the sample's omics layer,
enabled by the sample's ASPC, and supported by the corresponding data contract.
A missing tab normally means that the analysis is not enabled for that sample;
it does not mean that an enabled analysis returned no rows.

| DNA analysis | RNA analysis |
| --- | --- |
| Somatic SNVs | Fusions |
| Germline SNVs, when enabled | Expression, when enabled |
| CNVs | Classification, when enabled |
| DNA fusions or translocations | RNA QC, when enabled |
| Coverage | Reports |
| Biomarkers and PGX, when enabled |  |
| Reports |  |

### Overview

The Overview page shows the exact context used for review.

| Card | Content |
| --- | --- |
| Sample | Sample name, pairing, readiness, report state, case ID, and added time. |
| Analysis status | Raw and filtered counts for enabled analyses. |
| Sample meta | Omics, platform, sequencing scope, assembly, environment, ASP, ASPC, pipeline, purity, FFPE, and biomarkers. |
| Case and control | IDs, LIMS IDs, pool IDs, run, reads, FFPE state, and purity. |
| Files and QC | Declared inputs, required/optional state, availability, size, and record count. |
| Gene filters | Applied ISGLs and ad-hoc genes, separated by analysis type. |
| Configured filters | The filter snapshot stored on the sample, grouped by analysis. |

If a requested subpanel has no active ASPC, the application can resolve the
base ASPC and display a warning. Review that warning before clinical work.

## Work with clinical tables

All clinical tables use the same interaction model.

| Action | Behavior |
| --- | --- |
| Search | Filters supported columns across the complete result set. |
| Sort | Sorts the complete filtered result set before pagination. Select more headers to build a multi-column sort. |
| Select rows | Enables actions that apply to the selected findings. |
| Rows per page | Uses the user's table-page preference unless changed locally. |
| Export CSV | Exports normalized, non-duplicated values for the current table scope. |
| Open detail | Opens the finding and preserves the table state in the URL for return navigation. |

Mutation actions require confirmation. After a successful change, the
application invalidates the affected cached query and reloads persisted state.

### Markers and finding states

| Marker | Meaning |
| --- | --- |
| Tier 1 | Strong clinical significance. |
| Tier 2 | Potential clinical significance. |
| Tier 3 | Variant of uncertain significance. |
| Tier 4 | Benign or likely benign. |
| False positive | The finding is considered an analysis artefact. |
| Irrelevant | The finding is valid but outside the current clinical question. |
| Interesting | The finding is marked for attention; reporting still follows report rules and snapshot selection. |
| Blacklisted | The finding matches a blacklist decision. |
| Hotspot | Curated hotspot evidence is available. The detail tooltip shows the supported source records. |

Rows marked false positive, irrelevant, or blacklisted are visually subdued.
They remain available in the analysis view when requested but are excluded from
report output according to the report workflow.

## DNA review

### Small variants

The small-variant table presents the selected transcript together with sample
genotype data and annotation markers.

| Column group | Content |
| --- | --- |
| Info | OncoKB, ClinPGx, prescription, hotspot, and other compact evidence markers. |
| Identity | Gene, HGVS values, exon/intron, type, indel size, and genomic position. |
| Interpretation | Consequence, population frequency, tier, and finding flags. |
| Genotype | Case and optional control VAF, read counts, and supporting values. |

Population frequency is displayed to six decimal places when available. The
detail page provides transcript consequences, SIFT, PolyPhen, knowledgebase
links, comments, classifications, sample genotype, population frequencies, and
occurrence in other samples.

The selected transcript follows the configured transcript priority. Alternate
transcripts remain available in the transcript table and gene symbols link to
the gene information page. See
[DNA clinical review](clinical_review_dna.md) for the transcript and evidence
reference.

### CNVs

The CNV workspace can show the table and CNV profile in an adjustable split
view. The profile supports 0-degree and 90-degree orientation. The image grows
with its pane while preserving its aspect ratio.

CNV columns include genes, region, size, callers, copy number, purity, split
reads where supplied, status, and artefact evidence. Status and artefact are
separate because they describe different properties. Hover cards explain the
source counts and flags.

### DNA fusions and translocations

Structural finding tables show gene partners, breakpoints, type, HGVS or
event identity, caller, status, and available actions. Gene filtering uses the
ISGL selected for that analysis. It does not reuse an SNV list unless that list
was explicitly selected for the structural analysis.

### Coverage

Coverage is a DNA quality analysis. It is not a CNV profile. The page shows
low-coverage genes and regions, a searchable gene list, a scrollable zoomed
plot, exon/probe tables, and blacklist controls. Coverage does not display the
sample gene-panel card because its scope comes from the coverage data and
coverage configuration.

## RNA review

### Fusions

The RNA fusion table uses the same table, badge, sorting, filtering, export,
and action conventions as DNA tables.

| Column | Meaning |
| --- | --- |
| Gene 1 / gene 2 | Fusion partners. An applied fusion ISGL matches either partner. |
| Effect | In-frame or out-of-frame interpretation from the source result. |
| Spanning pairs / reads | Source support counts. |
| Fusion points | Breakpoint coordinates. |
| Tier | Saved classification when present. |
| Description | FusionCatcher evidence tags. Positive, negative, and context tags use separate colors. |
| Callers | Deduplicated normalized caller names. |

### Expression and classification

WTS samples can expose expression and classification in the same analysis
area. Expression lists gene TPM, reference mean, and a centered Z-score plot.
Classification lists class scores as comparable bars. These sections appear
only when enabled by the ASPC and loaded for the sample.

See [RNA clinical review](clinical_review_rna.md) for the complete column and
filter reference.

## Filters and gene lists

Filters are stored per sample and per analysis intent. Opening a filter panel
does not change results. Results change only after the user applies a valid
filter update.

| Filter family | Typical fields |
| --- | --- |
| Somatic SNV | Depth, alternate reads, VAF, control VAF, population frequency, consequence, ISGL, and ad-hoc genes. |
| Germline SNV | Germline policy, depth, frequency, consequence, and gene scope. |
| CNV | Size, gain/loss cutoffs, effect, CNV ISGL, and ad-hoc genes. |
| DNA translocation | Structural type and fusion/translocation gene list. |
| RNA fusion | Spanning pairs, spanning reads, caller, effect, description tags, and fusion ISGL. |
| Coverage | Warning/error cutoffs and coverage blacklist context. |

Gene scope is resolved separately for each analysis:

1. Use the ISGLs selected for that analysis.
2. If none are selected, use the ASP covered genes where defined.
3. If neither source defines genes, do not add a gene filter.

This rule prevents an SNV list from silently restricting CNVs or fusions.

## Comments and annotations

Comments use Markdown with edit and preview modes. Selecting an existing
visible comment can place its text into the editor as a draft.

| Comment type | Scope |
| --- | --- |
| Sample comment | One sample; the latest visible sample comment is used as the report summary. |
| Sample-specific finding comment | One finding in one sample. |
| Global annotation | A normalized finding identity across samples. |

Hidden comments are not shown by default. Users with permission to view hidden
comments can reveal them. A hidden comment is inactive: selecting its body does
not copy or apply it. Hide and unhide controls are shown only to authorized
users.

## Reports

Reports are previewed and saved inside a sample. The global Reports page lists
saved reports; it does not create a report outside a sample.

### Preview and save

| Stage | Stored state |
| --- | --- |
| Preview | Temporary render based on current sample state and report configuration. |
| Save | Report document, rendered artifact, report-rule identity/version, ASPC context, filter snapshot, and typed finding snapshots. |

The report table and snapshot can include every reportable analysis selected by
the ASPC: SNVs, CNVs, fusions, translocations, biomarkers, PGX, and other
released report sections. False-positive and irrelevant findings are excluded.

The report summary is the latest visible sample comment. If no visible sample
comment exists, the summary is empty. Preview and save do not create an
automatic replacement comment.

See [reporting and snapshots](../product/reporting_workflow_and_variant_snapshots.md)
and [clinical reporting rules](../product/clinical_reporting_rules.md) for the
authoritative report contract.

## Search and cohort review

| Page | Use |
| --- | --- |
| Tiered variant search | Search classification and annotation records across SNVs, CNVs, fusions, and translocations. Columns follow the finding nomenclature. |
| Gene cohort explorer | Summarize reported findings for one gene by assay group, tier, recurrence, and recorded sample sex. |
| Reported finding context | Open samples and report snapshots linked to a selected classified finding. |

Gene-cohort prevalence uses profiled samples in the applicable ASP or effective
sample gene-list scope as the denominator. By default, calculations use the
current reported occurrence for a sample. The historic option includes older
report snapshots but counts the same finding only once per sample.

## Notifications and profile

The notification menu shows messages addressed to the current user. Password
reset requests are visible to the administrative recipients responsible for
the request. Authorized administrators can broadcast a notification to all
users, selected roles, or selected accounts.

The Profile page contains safe account fields and user-owned UI settings.

| Setting | Effect |
| --- | --- |
| Analysis layout | Classic or Modern sample analysis presentation. |
| Samples layout | Classic or Modern sample worklist presentation. |
| Table page size | Default rows per page for supported tables. |
| Theme | Light or dark display. |

## Administration

Admin pages are permission-based. A user can receive access to one resource or
action without receiving unrestricted administration.

| Resource | Main actions |
| --- | --- |
| Users | View accounts; edit permitted profile, role, group, status, and authentication fields according to delegated permissions. |
| Roles | Assign permission policies and role metadata. System roles cannot be deleted. |
| Permissions | Review and filter permission policies. System permissions cannot be deleted. |
| ASP | Create, copy, import, export, view, and version assay definitions. |
| ASPC | Create, copy, import, export, view, and version assay configurations. |
| ISGL | Create, import, export, view, and version gene lists. |
| Samples | Review sample resources, edit raw JSON with live validation, or delete a sample and its owned dependent records. |
| Ingest | Submit and inspect sample-bundle ingest. |
| Application controls | Manage released module, task, maintenance, and retention settings. |
| Audit | Search security, configuration, ingest, report, and critical clinical workflow events. |
| Notifications | Send authorized broadcasts. |

ASP, ASPC, and ISGL updates create a new version with the same business ID and
make the previous version inactive. Existing samples and reports retain their
recorded configuration identity. An authorized reviewer can explicitly resolve
a sample to the latest compatible ASPC without silently replacing its stored
filter choices.

## Errors and missing data

| Message or state | Meaning | Action |
| --- | --- | --- |
| No information | The field is supported but no value was supplied. | Continue unless the field is required by the workflow. |
| No results | The analysis is available but the current query returned no rows. | Review filters and gene scope. |
| Missing tab | The analysis is not enabled or not valid for this sample. | Check ASPC analysis types and sample omics. |
| Base configuration in use | No active subpanel-specific ASPC was found. | Confirm that base behavior is clinically intended. |
| Request could not be completed | The API rejected a validly delivered request. | Read the detailed message and request path. |
| System action failed | An unexpected server or upstream failure occurred. | Record the time and request path for operations. |
| Module unavailable | An administrator disabled the module. | Contact the application operator. |

## Before completing a review

1. Confirm sample, case/control, ASP, ASPC, environment, and subpanel.
2. Review ingest files and analysis readiness.
3. Confirm the gene lists and filter values for each enabled analysis.
4. Review relevant findings and supporting evidence.
5. Save classifications, flags, and comments with the correct scope.
6. Preview the report and inspect every included analysis section.
7. Save the report only after the snapshot and rendered text are correct.

## Detailed references

| Subject | Reference |
| --- | --- |
| DNA review | [DNA clinical review](clinical_review_dna.md) |
| RNA review | [RNA clinical review](clinical_review_rna.md) |
| Coverage | [Coverage review](coverage_analytics.md) |
| Sample worklist | [Sample management](sample_management.md) |
| Dashboard | [Operational dashboard](operational_dashboard.md) |
| Page and column definitions | [UI page and table reference](../product/ui_page_table_reference.md) |
| Administration | [Management guide](management_guide.md) |
| Reporting | [Reporting workflow and snapshots](../product/reporting_workflow_and_variant_snapshots.md) |
| Query rules | [Query and filter strategy](../product/aspc_driven_query_strategy.md) |
