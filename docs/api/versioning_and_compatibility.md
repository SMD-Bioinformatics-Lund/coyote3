# API versioning and compatibility

Coyote3 publishes supported client routes under `/api/v1`. The OpenAPI schema
is the authoritative list of supported external routes. Hidden health and
internal integration routes are operational contracts and are not client APIs.

## Compatibility policy

Within `v1`, releases may add endpoints, optional request fields, response
fields, and enum values. Existing fields do not change meaning or type without
a new major API prefix. Clients must ignore response fields they do not use and
must not assume enums are permanently closed unless the contract says so.

An incompatible change follows this process:

1. Mark the route or field deprecated in OpenAPI and release notes.
2. Keep it functional for at least one published application release cycle.
3. Publish its replacement and migration instructions.
4. Remove it only in a new API major version, such as `/api/v2`.

Security fixes may shorten this period when retaining behavior would expose
clinical data or administrative capabilities. Such changes are called out in
the security and release documentation.

Python package organization is not part of the HTTP compatibility contract.
Router modules may move while URLs, permissions, and response contracts remain
stable.

## Runtime baseline

Production images use Python 3.12 on Debian Bookworm. This is the tested runtime
contract for Coyote3 4.0. A newer interpreter is adopted only after the API,
Celery, LDAP, MongoDB, and scientific dependencies pass the complete quality and
ingest suites; selecting the newest interpreter independently of that evidence
would weaken reproducibility.
