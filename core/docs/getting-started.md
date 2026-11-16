# Install and import the core

Python 3.12 or newer is required. From this package directory, install the project:

```bash
python -m pip install .
```

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
