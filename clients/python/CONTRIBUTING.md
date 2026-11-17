# Contributing

Use a focused branch from `dev` and open a pull request back to `dev`. Describe the
client behavior changed and link the issue. Keep server implementation changes in
the application repository.

- Preserve the public client interface and synchronous/asynchronous parity.
- Add relevant synthetic tests for behavior and failure handling.
- Run the [package tests and coverage](docs/development.md).
- Update affected documentation and [CHANGELOG.md](CHANGELOG.md).
- Update `pyproject.toml` when releasing a new package version.

Never include credentials, patient information or private deployment URLs in tests,
issues or examples. Use HTTPX mock transports for regression tests.

Follow [the release procedure](docs/releasing.md) for artifact verification and
versioning. Contributions retain the project's GPL-3.0-only license and existing
copyright and contributor notices.
