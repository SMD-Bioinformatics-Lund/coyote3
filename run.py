"""Flask UI entrypoint.

This launcher starts only the web presentation runtime (`wsgi.app`).
Business operations are handled by the separate FastAPI service.
"""

from wsgi import app
