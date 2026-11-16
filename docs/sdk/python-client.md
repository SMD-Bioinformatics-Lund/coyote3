# Integrate through the Python HTTP client {#python-sdk}

Use the HTTP client when a pipeline, notebook or external script accesses a
running Coyote deployment. Authentication, clinical rules, current permissions
and persistence remain on the server.

Start with the client-owned [getting-started guide](../../clients/python/docs/getting-started.md).
Use [resource and report operations](../../clients/python/docs/usage.md) for sample
reads, findings, pagination, asynchronous calls and reports. The
[reference](../../clients/python/docs/reference.md) describes response models and errors.

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
