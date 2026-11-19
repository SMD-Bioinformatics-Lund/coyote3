# Install and import Coyote Core

Python 3.12 or newer is required. From this package directory, install core:

```bash
python -m pip install .
```

The base installation includes all reusable data models and clinical validation,
with Pydantic, PyYAML and Bleach. It does not install a web host, database driver,
report renderer or alignment reader.

Select additional capabilities in the same distribution when required:

```bash
python -m pip install ".[reporting,alignment]"
```

`reporting` adds report construction and HTML/PDF rendering dependencies.
`alignment` adds pysam for alignment access and VCF ingestion. These extras
select dependencies; they do not create separate model implementations or versions.
A host using reporting or file ingestion must install the corresponding extra
before importing or executing those feature modules. The main application installs
both extras.

For an offline deployment, supply the built wheel and its dependencies through
the installation's artifact directory or package mirror. Public-index publication
of Coyote is not required.

Confirm the installed identity:

```python
from importlib.metadata import version
import coyote

assert coyote.__version__ == version("coyote-core")
```

Importing `coyote` does not initialize database connections, workers or an HTTP
application. Continue with [host integration](usage.md). If the host uses a center
profile, [select it first](configuration.md).
