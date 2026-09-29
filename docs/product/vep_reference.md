# VEP reference library

Open **About → VEP reference** to inspect the reference installed for an Ensembl
release. The page is public and does not expose sample data or import-operator
identities. Its address is `/about/vep`; a link such as
`/about/vep?version=103` selects a particular release.

## Selecting a release

The selector lists installed major releases, newest first. The initial selection
is the latest installed release unless the URL specifies another. An unavailable
release displays an error; the page never substitutes another release's definitions.
Use the release recorded in the sample's pipeline metadata when reviewing a finding.

## Definitions and diagrams

| View | Contents |
| --- | --- |
| Consequences | Consequence term, Coyote3 group, Ensembl impact, SO accession and full description |
| Variant classes | Variant-class names, SO accessions and definitions |
| Cache sources | Published cache versions for GRCh37 and GRCh38, not sample-specific pipeline versions |

Search accepts names, descriptions and SO accessions. Consequences can also be
filtered by group and impact. Tables initially show ten matching rows; **Show all**
reveals the remaining rows. SO links open Sequence Ontology's term pages:
`current_svn` for consequences and `current_release` for variant classes. Source
links open the selected release's Ensembl archive documentation, including the
cache documentation and the page containing the consequence diagram. These SO
pages are maintained by Sequence Ontology and are not snapshots of a VEP release.
Older Ensembl archives may be retired or redirected by Ensembl; the locally
installed definitions remain release-specific. Download URLs and checksums are
retained separately in the import provenance manifest.

The collapsible diagram shows consequence locations relative to a transcript.
It occupies only its own display width, preserves the original aspect ratio and
can be expanded to its native size with the zoom control. Narrow screens scroll
the enlarged image without widening the page.
Each release uses the image linked by its own Ensembl documentation source.
Images are served from the local knowledgebase, so viewing them requires no
request to Ensembl. A missing image is identified explicitly, without borrowing
one from another release.

Consequence badges in finding tables, finding details and transcript tables show
the release-specific description, impact, Coyote3 group and SO accession on hover
or keyboard focus when that metadata is available. Missing metadata is reported
as unavailable, rather than replaced with a definition from the latest release.

Ensembl impact describes a predicted molecular effect, not clinical pathogenicity.
Coyote3 groups are filtering categories. Historical website tables can differ
from the executable VEP engine; see the [source and import policy](../operations/vep_metadata_updates.md).

## Public API

| Endpoint | Response |
| --- | --- |
| `GET /api/v1/public/vep` | Installed major-release identifiers, sorted numerically |
| `GET /api/v1/public/vep/{release}` | Definitions, groups, cache metadata, source URLs and optional diagram for exactly that release |
| `GET /api/v1/public/vep/{release}/diagram` | Original image bytes for that release, with MIME type and SHA-256 ETag; 404 if absent |

These read-only endpoints require no authentication. The detail response excludes
database IDs and operator identity fields. Regular clinical metadata queries
exclude diagram bytes. The reference detail endpoint returns a compact diagram
descriptor; the browser fetches image bytes separately from the diagram endpoint.
