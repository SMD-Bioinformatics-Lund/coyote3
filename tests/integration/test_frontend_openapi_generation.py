"""Verify the URL-based generator against a running endpoint serving the actual API schema."""

import json
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from api.app.main import create_api_app


def test_running_schema_endpoint_matches_source_generated_frontend_types():
    root = Path(__file__).resolve().parents[2]
    if (
        shutil.which("npm") is None
        or not (root / "frontend/node_modules/@hey-api/openapi-ts").is_dir()
    ):
        pytest.skip("Install frontend generator dependencies to exercise URL-based generation")
    payload = json.dumps(create_api_app().openapi()).encode()

    class SchemaHandler(BaseHTTPRequestHandler):
        """Serve the real contract without any clinical application lifecycle dependencies."""

        def do_GET(self):
            """Return the schema only at the explicitly mounted OpenAPI URL."""
            if self.path != "/synthetic-center/api/v1/openapi.json":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            """Keep synthetic request details out of repository test output."""

    with ThreadingHTTPServer(("127.0.0.1", 0), SchemaHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/synthetic-center/api/v1/openapi.json"
            result = subprocess.run(
                ["npm", "--prefix", "frontend", "run", "api:check", "--", "--url", url],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert result.returncode == 0, result.stdout + result.stderr
        finally:
            server.shutdown()
            thread.join(timeout=5)
