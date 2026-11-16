# Installation

Python 3.12 or newer is required. Choose the checkout instructions when working
in this repository, or release wheels for an independent installation.

## Use the source checkout

Run from the repository root:

```bash
uv sync --all-packages
.venv/bin/coyote-atlas inspect
.venv/bin/coyote-atlas validate
```

`inspect` displays the bundle identity and datasets. `validate` checks the
packaged resources and exits successfully only if their integrity and contracts
are valid. Neither command needs a running application.

## Install from release wheels

Use your organization's reviewed artifact directory, containing Atlas and its
core, client and third-party dependencies. Replace `/path/to/wheels` with that
directory. Public PyPI publication is not required.

```bash
python -m pip install --no-index --find-links /path/to/wheels coyote-atlas==1.0.0
coyote-atlas inspect
coyote-atlas validate
```

These commands need no environment file, MongoDB, FastAPI or running Coyote
server. The package carries its data; the current working directory does not
select a different reference source.

## Add Atlas to a server

The standard application image already includes Atlas. For a separately installed
server, expose reference planning and installation routes by installing Atlas with the
server and restart that API using your normal deployment procedure:

```bash
python -m pip install --no-index --find-links /path/to/wheels 'coyote-atlas[api]==1.0.0'
```

The server discovers `coyote.api.routers` and `coyote.reference_bundles` entries.
Installation makes routes available; it does not populate collections. Use the
[reviewed installation workflow](usage.md) when reference installation is intended.
