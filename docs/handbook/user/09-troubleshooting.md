# Troubleshooting (User)

## Cannot access page

Likely causes:

- not logged in
- missing permission or insufficient role level
- no assay access for requested sample

Action:

- confirm login
- ask admin to review role/permissions and assay assignment

## Empty sample lists

Likely causes:

- user assay/env scope mismatch
- restrictive filters/search terms

Action:

- clear search/filter
- verify assay scope with admin

## Report opens but file missing

Likely causes:

- report file not present on mounted filesystem
- incorrect `REPORTS_BASE_PATH` or assay report folder mapping

Action:

- notify operations/admin to verify report path configuration and storage availability

## Unexpected variant volume

Likely causes:

- incorrect filter settings
- no ISGL/ad-hoc gene constraints for the case

Action:

- revisit sample settings (`/samples/<sample_id>/edit`)
- verify effective genes list
