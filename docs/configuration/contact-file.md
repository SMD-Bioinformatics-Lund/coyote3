# Contact file: contact.toml

This file controls center-specific content shown on Contact and About pages,
and the optional center identity and contact details in modern report headers.
Repository links and the product description are intentionally not present;
they are codebase metadata and remain consistent across deployments.

The documentation footer also displays this public center identity. It reads
`organization.department` from this file and uses `ORGANIZATION_NAME` for the
organization name when supplied, otherwise `organization.name`. Compose passes
the organization name into the documentation image build. Rebuild the docs image
after changing these values; for the development overlay's mounted `site/`, rebuild
the site with the intended `ORGANIZATION_NAME` exported in the build environment.
Only organization and department are included in the footer, not support contacts.

## Format and omission behavior

TOML uses `[section]` for a named group of keys, and `[[contacts]]` or `[[hours]]`
for another item in a list. Quotes delimit text; `#` starts a comment.
The selected external directory must contain this file, even if optional lists
are empty. The loader accepts TOML and supplies empty structures for missing
sections; it does not enforce all editorial recommendations below or validate
email addresses. Review public content before publishing it.

| Key | Required / recommended | Default if omitted | Meaning |
| --- | --- | --- | --- |
| `organization` | Recommended table | Empty metadata, then application identity fields are added | Center metadata. |
| `organization.name` | Recommended text | Runtime name comes from `ORGANIZATION_NAME` (`Coyote3` by default); the docs hook can use file identity when no override is supplied | Keep the center name aligned with the environment. |
| `organization.department` | Optional text | Not supplied | Laboratory or department shown with the center identity. |
| `organization.report_logo` | Optional text | `region-skane` | Modern report logo: bundled mark, a supported image path inside the center directory, or empty to omit. |
| `organization.accreditation_logo` | Optional text | Not supplied | SVG, PNG or JPEG inside the center directory, or an absolute host path imported by the Compose wrapper before container creation. Printed in the PDF footer only when the applied ASP snapshot has `accredited = true`. Empty omits it. |
| `organization.address` | Optional text | Not supplied | Postal address printed below the center name in modern reports. Newlines are retained. |
| `organization.phone` | Optional text | Not supplied | Center contact number printed with a telephone icon in modern reports. This is separate from the support escalation number. |
| `support` | Recommended table | Empty table, with available generated links added | Public support information. |
| `support.primary_email` | Recommended text | Not supplied | General support mailbox. |
| `support.urgent_phone` | Optional text | Not supplied | Approved telephone/escalation route. |
| `support.web_app_base_url` | Normally generated | Public origin plus prefix and trailing slash, when origin is configured | Application link; an explicit file value is retained. |
| `support.help_center_url` | Normally generated | Public origin plus prefix and `/docs-site/`, when origin is configured | Documentation link; an explicit file value is retained. |
| `hours` | Optional array of tables | Empty list | Service hours. |
| `hours[].label`, `hours[].value` | Recommended text when a row exists | Not supplied | Row heading and schedule/escalation text. |
| `contacts` | Recommended array of tables | Empty list | Public contact cards. |
| `contacts[].label`, `contacts[].description` | Recommended text when a card exists | Not supplied | Card title and which questions belong there. |
| `contacts[].role`, `contacts[].phone` | Optional text | Not supplied | Responsibility and telephone details. |
| `contacts[].email` | Optional legacy single-recipient text | Not supplied | Prefer the `people` list for new contact cards. |
| `contacts[].people` | Optional array of tables | No recipients supplied | Named recipients within a contact card. |
| `contacts[].people[].name`, `contacts[].people[].email` | Recommended text for each recipient | Not supplied | Display name and mailbox used for an email link. |

## Example

```toml
[organization]
name = "Example Molecular Diagnostics Center"
department = "Molecular Diagnostics"
address = "Example Road 1, 12345 Example City"
phone = "+46 00 123456"
accreditation_logo = "" # For example, "assets/accreditation.svg" when configured.

[support]
primary_email = "support@example.org"
urgent_phone = ""

[[hours]]
label = "Support hours"
value = "Weekdays 09:00–16:00, Europe/Stockholm"

[[contacts]]
label = "Platform support"
description = "Account access and application availability."

[[contacts.people]]
name = "Support team"
email = "support@example.org"
```

These are synthetic example values, not a default center identity. Restart/recreate
the application processes to load reviewed changes and rebuild the documentation
image for footer changes. No database migration is required for public contact text.

Repository URLs, issue templates, product description, documentation links,
and catalog links are intentionally not configurable per center. They are
loaded from `api/config/application_metadata.py`, because they identify the
Coyote3 software project rather than the deploying organization.

## Swedac accreditation artwork

For Docker deployments, `organization.accreditation_logo` may initially contain
an absolute path to an SVG, PNG, or JPEG on the Docker host:

```toml
[organization]
accreditation_logo = "/srv/branding/swedac.svg"
```

Before `up`, `create`, `start`, or `run`, `scripts/deployment/compose-with-version.sh`
copies that file into `logos/` inside the mounted center configuration directory.
It rewrites the host's `contact.toml` to a relative path such as
`logos/accreditation-<sha256>.svg`, which the container resolves under
`/app/center-config`. Existing manifest checksums are updated for the contact file
and copied logo. The host user running the wrapper needs write access to the center
directory; the container mount remains read-only. The original image is unchanged.
Empty and relative settings are left unchanged on subsequent runs. To replace the
image, set the absolute host path again before recreating the containers.

This preparation runs on the host, before container creation. A direct Docker build
or direct `docker compose` command does not perform it; use the wrapper. Missing
source files or unsupported file extensions stop preparation.

For issued reports, obtain the center's complete accreditation symbol from
[Swedac Mina sidor](https://minasidor.swedac.se/). Swedac supplies each accredited
organization's symbol with its number and standard. Store that original inside
the external center directory and select it using `organization.accreditation_logo`.
See [Swedac's symbol guidance](https://www.swedac.se/tjanster/ackreditering/ackreditering-sa-fungerar-det/ackrediteringssymbolen/).

The configured artwork follows the medical-laboratory layout in Annex 1, in order:

1. The circular Swedac accreditation mark.
2. `Ackred. nr 1309`, with the center's assigned accreditation number.
3. `Provning`.
4. `ISO 15189`.

The layout and standard wording come from
[STAFS 2020:1, consolidated 2026-10-01, Annex 1](https://regelverk.swedac.se/foreskrifter/swedac/stafs-2020-1-konsol.html).
Section 14 permits the specified blue/yellow colors, black or white against a
contrasting background. Section 13 requires the accredited organization's name,
mark or logo near the accreditation reference.

[Swedac DOC 20:1, edition 7](https://regelverk.swedac.se/policy/swedac-doc-20-1_sv.html)
states that Swedac supplies the report symbols and that these must not be modified.
The symbol must not dominate the accredited organization's identity. Reports
containing both accredited and non-accredited results must clearly identify the
results outside accreditation.

### Dimensions and example SVG

Swedac's supplied **Information om ackrediteringssymbol**, SWEDAC INFO 17:5,
version 3.0, page 3 specifies a minimum width of **25 mm** for SVG artwork.
The modern report footer renders the complete symbol at that width and preserves
its proportions. Do not crop, recolor, retype or reconstruct the issued artwork.
Verify all wording in the final PDF at its actual printed size.

The guide permits the supplied blue/yellow, black and white versions, with good
contrast against the background. The original black SVG is suitable for the white
report paper and avoids dependence on CMYK/ICC rendering. The blue/yellow SVG can
also be selected for digital output. Preserve its supplied color values; the
report's purple/orange theme must not recolor the accreditation symbol.

The [example SVG](../assets/examples/reporting/swedac-iso-15189-example.svg) has a
compact 24 mm by 28 mm canvas and uses Swedac's published vector paths in black.
Those are the example's intrinsic dimensions; the footer scales it to 25 mm wide.
The information
lines sit directly below the circular mark and display `Ackred. nr 1309`,
`Provning` and `ISO 15189`. The example center configuration selects an identical
copy under `logos/`. Review the accreditation number for the deploying center and
use the center's issued symbol for clinical reports.

![Swedac ISO 15189 artwork with accreditation number 1309](../assets/examples/reporting/swedac-iso-15189-example.svg)

The modern report footer uses a 25 mm wide image area with proportional height.
The example renders at approximately 25 mm by 29.17 mm; an issued 184 × 209 SVG
renders at approximately 25 mm by 28.40 mm. Self-contained WOFF2 fonts in supplied
SVG stylesheets are supported and remain embedded. External font/image references,
scripts and active SVG content remain prohibited.
Reports displaying an accreditation logo reserve a 38 mm bottom margin; other
reports retain a 22 mm margin. Check the center's complete symbol and its wording
at 100% print scale when selecting the artwork.
