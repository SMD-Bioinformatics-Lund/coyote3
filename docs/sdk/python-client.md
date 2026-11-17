# Integrate through the Python HTTP client {#python-sdk}

Use the HTTP client when a pipeline, notebook or external script accesses a
running Coyote deployment. Authentication, clinical rules, current permissions
and persistence remain on the server.

Start with the client-owned [getting-started guide](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient/blob/dev/docs/getting-started.md).
Use [resource and report operations](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient/blob/dev/docs/usage.md) for sample
reads, findings, pagination, asynchronous calls and reports. The
[reference](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient/blob/dev/docs/reference.md) describes response models and errors.

## Application integration

Supply the deployment's public URL, including its mount prefix and excluding
`/api/v1`. Arrange an account or supported token through the installation's
authentication process. A client object does not grant assay or environment access.

The server's OpenAPI document defines the available HTTP paths. The client's
typed methods and general endpoint objects send requests through that contract.
An additive client method does not create a server endpoint.

For deployment-side credentials and sample submission, see
[authentication](../api/authentication.md) and
[sample ingestion](../api/sample-ingestion.md).
For software-version selection, see [release compatibility](compatibility.md).

A trusted in-process host uses [core application operations](application-sdk.md)
instead of calling the server over HTTP.

## Application dependency and private access

The client source, unit tests and package documentation live in its own repository.
This application selects a full Git commit in `pyproject.toml` and records the
resolution in `uv.lock`. `release.toml` retains the selected package version.
There is no client source copy or submodule in this repository.

Native installation requires a Git credential helper with repository read access.
The installer prepares a checksum-verified wheel in `.release/client` before
Docker builds; run `./install.sh dependencies` before invoking Docker directly.
The same prepared artifact supports modern and legacy images. GitHub credentials
are never copied into those images.

Application GitHub Actions requires `COYOTE_PYCLIENT_READ_TOKEN`, a repository or
organization Actions secret restricted to **Contents: read** on the private client
repository. The default `GITHUB_TOKEN` cannot read another private repository.
Configure that secret before running the application workflow. Do not put it in
a tracked environment file or dependency URL.
The application workflow does not publish its uv cache because it contains private
client sources and wheels.

To adopt a new client revision, update its full commit in uv sources, run `uv lock`,
update `client_version` when the package version changes, and run the application's
client/OpenAPI and installed-artifact checks. Record the adoption in the application
changelog. Client releases and their version notes remain owned by its repository.
