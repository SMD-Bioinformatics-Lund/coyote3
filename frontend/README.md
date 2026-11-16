# Coyote frontend

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![Node: >=22](https://img.shields.io/badge/Node-%3E%3D22-339933?style=flat&logo=nodedotjs&logoColor=white) ![UI: React 19](https://img.shields.io/badge/UI-React%2019-087EA4?style=flat&logo=react&logoColor=white) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

The browser application for sample review, clinical configuration, findings and
report workflows. React renders the interface and calls the versioned HTTP API.
Clinical rules and authoritative permission checks remain on the server.

## Documentation

Start with the [frontend guide](docs/README.md), then use:

- [Getting started](docs/getting-started.md) for a local development server.
- [Configuration](docs/configuration.md) for proxy and presentation settings.
- [Architecture](docs/architecture.md) for UI responsibilities.
- [Development](docs/development.md) for checks, contracts and production builds.

The frontend is a private Node application. Its tools and dependencies are in
[package.json](package.json). Application release identity comes from
`release.toml` at the repository root.

Badges describe technology and metadata. See the application
[license](LICENSE.txt), [copyright and affiliation](COPYRIGHT.txt) and
[additional notices](NOTICE.txt). Production builds include these three files.
