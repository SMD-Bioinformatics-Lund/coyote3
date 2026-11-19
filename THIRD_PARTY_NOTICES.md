# Third-party notices

The COYOTE4 application license does not replace licenses or attribution
requirements for third-party components. Their respective holders retain their
rights. Components expressly identified under separate terms retain those terms.

## Dependency inventories

- Python runtime dependencies: [pyproject.toml](pyproject.toml) and
  [requirements.txt](requirements.txt). Installed distributions provide their
  own license metadata and license files.
- Relay dependencies: [services/relay/pyproject.toml](services/relay/pyproject.toml).
- Atlas carries reference-resource attribution and dependency notices in its
  installed distribution; see [Atlas documentation](docs/core/README.md#coyote-atlas).
- Frontend dependencies: [frontend/package.json](frontend/package.json) and its
  lockfile. Dependencies retain their packaged copyright and license notices.
- Documentation and repository tooling: [package.json](package.json) and
  [pyproject.toml](pyproject.toml).
- Modern report rendering: `smd-reports` 0.5.3, distributed under
  `GPL-3.0-only` according to its installed package metadata. Retain its packaged
  license and the notices for its report fonts and artwork.
- Base images, operating-system packages and fonts: installation declarations
  in [docker/Dockerfile](docker/Dockerfile) and the other deployment Dockerfiles.
  Their installed distributions retain their own notices.

## Bundled materials

- [Logo sources and attribution](frontend/public/logos/README.md).
- [Local icon sources and attribution](frontend/public/icons/README.md)
  (Lucide Icons and Contributors, ISC).
- [Coyote Relay license](services/relay/LICENSE.txt).

Knowledgebase data, institutional insignia and third-party marks are subject to
their respective terms. Their use in COYOTE4 does not grant ownership, trademark
rights or endorsement.

This file identifies authoritative manifests and existing notices. It is not a
complete dependency-license inventory or certification of redistribution
compatibility. Authorized distributors must retain the notices for the actual
versions and materials included in their distribution.
