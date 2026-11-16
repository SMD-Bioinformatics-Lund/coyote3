# Installation

Python 3.12 or newer is required. Install a reviewed Atlas wheel and its pinned
core/client dependencies from your organization's package source:

```bash
pip install coyote-atlas
coyote-atlas inspect
coyote-atlas validate
```

These commands need no environment file, MongoDB, FastAPI or running Coyote
server. The package carries its data; the current working directory does not
select a different reference source.

To expose reference planning and installation routes, install Atlas with the
server and restart that API using your normal deployment procedure:

```bash
pip install 'coyote-atlas[api]'
```

The server discovers `coyote.api.routers` and `coyote.reference_bundles` entries.
Installation makes routes available; it does not populate collections. Use the
[reviewed installation workflow](usage.md) when reference installation is intended.
