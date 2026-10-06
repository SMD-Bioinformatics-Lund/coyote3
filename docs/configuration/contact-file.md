# Contact file: contact.toml

This file controls center-specific content shown on Contact and About pages.
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
