# Python HTTP client

[Coyote pyClient](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient) is an
independent package for external applications, notebooks and integrations. It is
not installed by the Coyote application. Its source, unit tests and optional server
compatibility checks live in that repository, which is currently private.

See its [usage guide](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient/blob/dev/docs/usage.md)
and [development guide](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient/blob/dev/docs/development.md).
The application's own HTTP administration tools use HTTPX directly. Core and the
API do not call the Python client to perform application operations.
