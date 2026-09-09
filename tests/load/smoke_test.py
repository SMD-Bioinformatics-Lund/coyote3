"""Run real Locust subprocesses against a synthetic stdlib HTTP server only.

Execute with the isolated interpreter that has requirements-load.txt installed:
python tests/load/smoke_test.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from support import ROUTES

HERE = Path(__file__).resolve().parent
FLOWS = [
    "browsing",
    "findings",
    "dashboard",
    "genes",
    "reports",
    "report_preview",
    "rule_testing",
    "comments",
    "ingest",
]


class SyntheticHandler(BaseHTTPRequestHandler):
    """Serve canned API-shaped responses without clinical data or application imports."""

    def log_message(self, format, *args):
        """Suppress request logging so identifiers never enter smoke output.

        Args:
            format: Unused standard HTTP logging format.
            *args: Unused logging values.
        """

    def do_GET(self):
        """Handle a synthetic read or task status request."""
        self.respond()

    def do_POST(self):
        """Handle a synthetic session, preview, comment, or ingest request."""
        self.respond()

    def do_DELETE(self):
        """Handle synthetic logout only."""
        self.respond()

    def respond(self):
        """Validate mount, cookies, CSRF, and fixed paths before sending canned JSON."""
        path = urlsplit(self.path).path
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        body = json.loads(raw) if raw else None
        self.server.seen.append((self.command, path, body))
        prefix = "/mounted/api/v1"
        if not path.startswith(prefix):
            self.send_json({"error": "unexpected path"}, 404)
            return
        path = path[len(prefix) :]
        if path == "/public/about":
            if self.server.mode == "redirect":
                self.send_response(302)
                self.send_header("Location", "/redirect-trap")
                self.end_headers()
                return
            self.send_json(
                {
                    "application": {
                        "environment": "production" if self.server.mode == "production" else "test",
                        "script_name": "/mounted",
                    },
                    "databases": {
                        "primary": "stub",
                        "identity": "stub_identity",
                        "bam_service": "stub_bam",
                    },
                }
            )
            return
        if path == "/auth/sessions" and self.command == "POST":
            if not body or body.get("provider") != "local":
                self.send_json({"error": "invalid credentials shape"}, 400)
                return
            self.send_json({"status": "ok", "csrf_token": "stub-csrf", "user": {}}, cookie=True)
            return
        if self.headers.get("Cookie") != "stub_session=synthetic":
            self.send_json({"error": "missing session"}, 401)
            return
        if self.command != "GET" and self.headers.get("X-CSRF-Token") != "stub-csrf":
            self.send_json({"error": "missing CSRF"}, 403)
            return
        if path == "/auth/sessions/current" and self.command == "DELETE":
            self.send_json({"status": "ok"})
        elif self.server.mode == "rate_limit":
            self.send_json({"error": "synthetic rate limit"}, 429)
        elif path == "/samples":
            self.send_json({"live_samples": [{"name": "demo_dna_sample"}], "done_samples": []})
        elif path == "/samples/demo_dna_sample/small-variants":
            self.send_json({"sample": {"name": "demo_dna_sample"}, "variants": []})
        elif path == "/samples/demo_dna_sample/small-variants/demo_small_variant":
            self.send_json(
                {"sample": {"name": "demo_dna_sample"}, "variant": {"_id": "demo_small_variant"}}
            )
        elif path == "/dashboard/metrics/samples":
            self.send_json({"metric_meta": {"stale": False}})
        elif path == "/common/gene/BRAF/info":
            self.send_json({"gene": {"symbol": "BRAF"}})
        elif path == "/reports":
            self.send_json({"reports": [], "total": 0})
        elif path == "/samples/demo_dna_sample/reports/dna/preview":
            self.send_json({"sample": {}, "meta": {}, "report": {"html": "<p>Synthetic</p>"}})
        elif (
            path
            == "/admin/clinical-rule-sets/versions/demo_rule_version/test-samples/demo_dna_sample/preview"
        ):
            self.send_json({"sample": {}, "rule_set": {}, "evaluation": {}, "persisted": False})
        elif path == "/samples/demo_dna_sample/comments" and self.command == "POST":
            self.send_json({"status": "ok", "resource": "sample_comment", "action": "add"}, 201)
        elif path == "/internal/ingest/sample-bundle/async" and self.command == "POST":
            if body.get("update_existing") is not False or body.get("increment") is not False:
                self.send_json({"error": "unsafe ingest"}, 400)
                return
            self.send_json({"status": "accepted", "task_id": "stub-task"}, 202)
        elif path == "/internal/tasks/stub-task":
            self.send_json(
                {
                    "status": "ok",
                    "task_id": "stub-task",
                    "state": "SUCCESS",
                    "ready": True,
                    "successful": True,
                    "result": {
                        "status": "error" if self.server.mode == "task_failure" else "ok",
                        "sample_id": "stub-sample",
                    },
                }
            )
        else:
            self.send_json({"error": "unexpected route"}, 404)

    def send_json(self, body: dict, status: int = 200, cookie: bool = False):
        """Send one JSON response, optionally establishing the synthetic cookie session.

        Args:
            body: Canned JSON object.
            status: HTTP status code, default 200.
            cookie: Whether to set the fake session cookie.
        """
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        if cookie:
            self.send_header("Set-Cookie", "stub_session=synthetic; Path=/; HttpOnly")
        self.end_headers()
        self.wfile.write(encoded)


class LocustSmokeTests(unittest.TestCase):
    """Verify real HTTP sessions, failure accounting, and deployment safety in subprocesses."""

    def run_locust(self, mode: str, flows: list[str], host_override: bool = False):
        """Execute a short bounded headless load test against loopback only.

        Args:
            mode: Synthetic server behavior switch.
            flows: One workflow per account, ensuring each is exercised.
            host_override: Whether to supply a deliberately mismatched CLI host.

        Returns:
            Process return code, parsed metric rows, and recorded stub requests.
        """
        with tempfile.TemporaryDirectory(prefix="coyote3-load-smoke-") as directory:
            root = Path(directory)
            server = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticHandler)
            server.mode, server.seen = mode, []
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                cfg = json.loads((HERE / "config.example.json").read_text())
                cfg.update(
                    target_url=f"http://127.0.0.1:{server.server_port}/mounted",
                    databases={
                        "primary": "stub",
                        "identity": "stub_identity",
                        "bam_service": "stub_bam",
                    },
                    allow_writes=True,
                    think_time_seconds=[0.1, 0.1],
                    poll_interval_seconds=0.1,
                    request_timeout_seconds=2,
                )
                (root / "config.json").write_text(json.dumps(cfg))
                (root / "fixtures.example.json").write_text(
                    (HERE / "fixtures.example.json").read_text()
                )
                (root / "credentials.json").write_text(
                    json.dumps(
                        {
                            "accounts": [
                                {
                                    "username": f"stub-{i}",
                                    "password": "synthetic-stub-only",
                                    "provider": "local",
                                    "workflows": [flow],
                                }
                                for i, flow in enumerate(flows)
                            ]
                        }
                    )
                )
                env = {k: v for k, v in os.environ.items() if not k.startswith("LOCUST_")}
                env.update(
                    COYOTE3_LOAD_CONFIG=str(root / "config.json"),
                    COYOTE3_LOAD_CREDENTIALS=str(root / "credentials.json"),
                )
                command = [
                    sys.executable,
                    "-m",
                    "locust",
                    "-f",
                    str(HERE / "locustfile.py"),
                    "--headless",
                    "--users",
                    str(len(flows)),
                    "--spawn-rate",
                    "20",
                    "--run-time",
                    "3s",
                    "--stop-timeout",
                    "3",
                    "--only-summary",
                    "--csv",
                    str(root / "metrics"),
                    "--json-file",
                    str(root / "final"),
                    "--exit-code-on-error",
                    "1",
                ]
                if host_override:
                    command.extend(["--host", "http://127.0.0.1:1"])
                result = subprocess.run(
                    command,
                    env=env,
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=25,
                    check=False,
                )
                metrics = root / "metrics_stats.csv"
                self.assertTrue(metrics.is_file(), "Locust did not produce metrics")
                # Periodic CSV snapshots can precede logout; JSON is written after user teardown.
                final = root / "final.json"
                self.assertTrue(final.is_file(), "Locust did not produce final metrics")
                rows = [
                    {
                        "Name": row["name"],
                        "Request Count": row["num_requests"],
                        "Failure Count": row["num_failures"],
                    }
                    for row in json.loads(final.read_text())
                ]
                return result.returncode, rows, server.seen.copy()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_all_workflows(self):
        """Exercise each workflow, cookie session, CSRF, and terminal ingest metric."""
        code, rows, seen = self.run_locust("success", FLOWS)
        self.assertEqual(code, 0)
        self.assertTrue(all(int(row["Failure Count"]) == 0 for row in rows))
        names = {row["Name"] for row in rows}
        for route in ROUTES.values():
            self.assertIn(route[1], names)
            metric = next(row for row in rows if row["Name"] == route[1])
            self.assertGreater(int(metric["Request Count"]), 0)
        self.assertIn("ingest/terminal", names)
        self.assertIn("/api/v1/samples/{sample_id}/small-variants/{finding_id}", names)
        self.assertFalse(any("demo_" in name or "stub-task" in name for name in names))
        logins = [p for method, p, _ in seen if p.endswith("/auth/sessions") and method == "POST"]
        logouts = [
            p for method, p, _ in seen if p.endswith("/sessions/current") and method == "DELETE"
        ]
        self.assertEqual(len(logins), len(FLOWS))
        self.assertEqual(len(logouts), len(FLOWS))
        self.assertFalse(any("/publish" in p or "/retire" in p for _, p, _ in seen))

    def test_preflight_refusals(self):
        """Reject production and redirects before login; never follow the redirect trap."""
        for mode in ["production", "redirect"]:
            with self.subTest(mode=mode):
                code, _, seen = self.run_locust(mode, ["dashboard"])
                self.assertNotEqual(code, 0)
                self.assertTrue(seen)
                self.assertTrue(all(p.endswith("/public/about") for _, p, _ in seen))

    def test_visible_failures(self):
        """Keep rate limits and HTTP-200 terminal domain errors visible as failures."""
        for mode, flow in [("rate_limit", "dashboard"), ("task_failure", "ingest")]:
            with self.subTest(mode=mode):
                code, rows, _ = self.run_locust(mode, [flow])
                self.assertNotEqual(code, 0)
                self.assertTrue(any(int(row["Failure Count"]) > 0 for row in rows))
                if flow == "ingest":
                    terminal = next(row for row in rows if row["Name"] == "ingest/terminal")
                    self.assertGreater(int(terminal["Failure Count"]), 0)

    def test_host_override(self):
        """Abort mismatched Locust host overrides without transmitting any request."""
        code, _, seen = self.run_locust("success", ["dashboard"], host_override=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
