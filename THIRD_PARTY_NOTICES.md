# Third-party notices

The COYOTE3 application license does not replace licenses or attribution
requirements for third-party components. Their respective holders retain their
rights. Components expressly identified under separate terms retain those terms.

## Dependency inventories

- Python runtime dependencies: [pyproject.toml](pyproject.toml) and
  [requirements.txt](requirements.txt). Installed distributions provide their
  own license metadata and license files.
- Independent Python client dependencies:
  [clients/python/pyproject.toml](clients/python/pyproject.toml).
- Frontend dependencies: [frontend/package.json](frontend/package.json) and its
  lockfile. Dependencies retain their packaged copyright and license notices.
- Documentation and repository tooling: [package.json](package.json) and
  [pyproject.toml](pyproject.toml).
- Base images, operating-system packages and fonts: installation declarations
  in [docker/Dockerfile](docker/Dockerfile) and the other deployment Dockerfiles.
  Their installed distributions retain their own notices.

## Bundled materials

- [Reference catalog notice](api/bootstrap/catalogs/reference/NOTICE.txt).
  The bundled Ensembl-derived materials retain their
  [Apache License 2.0](api/bootstrap/catalogs/reference/LICENSE.txt).
- [Logo sources and attribution](frontend/public/logos/README.md).
- [Local icon sources and attribution](frontend/public/icons/README.md)
  (Lucide Icons and Contributors, ISC).
- [Independent Python client license](clients/python/LICENSE.txt).

Knowledgebase data, institutional insignia and third-party marks are subject to
their respective terms. Their use in COYOTE3 does not grant ownership, trademark
rights or endorsement.

This file identifies authoritative manifests and existing notices. It is not a
complete dependency-license inventory or certification of redistribution
compatibility. Authorized distributors must retain the notices for the actual
versions and materials included in their distribution.
