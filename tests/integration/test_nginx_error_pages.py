"""Exercise browser error pages through an isolated local Nginx proxy."""

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "nginx:1.27-alpine"


@pytest.fixture(scope="module", params=["", "/coyote3"])
def error_proxy(request, tmp_path_factory):
    """Start a synthetic proxy on loopback without touching application services."""
    if not shutil.which("docker"):
        pytest.skip("Local Docker is required for Nginx integration checks")
    context = subprocess.run(
        ["docker", "context", "inspect", "--format", '{{(index .Endpoints "docker").Host}}'],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    if not context.startswith("unix://"):
        pytest.skip("Nginx checks require a local Unix Docker socket")
    docker = ["docker", "--host", context]
    available = subprocess.run(
        [*docker, "image", "inspect", IMAGE], capture_output=True, timeout=10
    )
    if available.returncode:
        pytest.skip("The local Nginx test image is unavailable; no images are pulled")
    directory = tmp_path_factory.mktemp("nginx-errors")
    output = directory / "proxy.conf"
    prefix = request.param
    subprocess.run(
        ["sh", str(ROOT / "deploy/compose/nginx/render-config.sh")],
        env={
            **os.environ,
            "SCRIPT_NAME": prefix,
            "COYOTE3_NGINX_OUTPUT_PATH": str(output),
            "COYOTE3_NGINX_FRONTEND_UPSTREAM": "http://127.0.0.1:8090",
            "COYOTE3_NGINX_API_UPSTREAM": "http://127.0.0.1:8090",
            "COYOTE3_NGINX_DOCS_UPSTREAM": "http://127.0.0.1:1",
            "COYOTE3_NGINX_PUBLIC_SCHEME": "https",
        },
        capture_output=True,
        check=True,
        timeout=10,
    )
    rendered = output.read_text()
    rendered = rendered.replace(
        "access_log syslog:server=monitor:5514,tag=proxy,severity=info combined;",
        "access_log off;",
    ).replace("error_log syslog:server=monitor:5514,tag=proxy error;", "error_log /dev/stderr;")
    output.write_text(rendered)
    synthetic_locations = "\n".join(
        f'location ~ /fault/{code}$ {{ return {code} "synthetic upstream"; }}'
        for code in [401, 403, 404, 500, 502, 503, 504]
    )
    (directory / "nginx.conf").write_text(
        "events {}\nhttp {\ninclude /etc/nginx/mime.types;\n"
        "server { listen 8090;\n"
        'location /api/ { default_type application/json; return 503 \'{"detail":"synthetic API error"}\'; }\n'
        'location ~ /healthy$ { return 200 "synthetic healthy page"; }\n'
        f'{synthetic_locations}\nlocation / {{ return 503 "synthetic upstream"; }}\n}}\n'
        "include /etc/nginx/test/proxy.conf;\n}\n"
    )
    container = subprocess.run(
        [
            *docker,
            "run",
            "--rm",
            "--detach",
            "--pull=never",
            "--publish",
            "127.0.0.1::8088",
            "--mount",
            f"type=bind,src={directory},dst=/etc/nginx/test,readonly",
            "--mount",
            f"type=bind,src={ROOT / 'deploy/compose/nginx/error-pages'},dst=/etc/nginx/error-pages,readonly",
            IMAGE,
            "nginx",
            "-c",
            "/etc/nginx/test/nginx.conf",
            "-g",
            "daemon off;",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    ).stdout.strip()
    try:
        published = subprocess.run(
            [*docker, "port", container, "8088/tcp"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        origin = f"http://{published}"
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"{origin}{prefix}/healthy", timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            pytest.fail("Synthetic Nginx did not become ready")
        yield origin, prefix
    finally:
        subprocess.run([*docker, "stop", "--time=1", container], capture_output=True, timeout=10)


def _response(origin, path, *, method="GET", headers=None):
    """Return status, headers and body for success and HTTP error responses."""
    request = urllib.request.Request(f"{origin}{path}", method=method, headers=headers or {})
    try:
        response = urllib.request.urlopen(request, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read().decode()


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_browser_errors_keep_status_and_security_headers(error_proxy, code):
    """Replace only browser server-error bodies, without caching or leaking the request."""
    origin, prefix = error_proxy
    status, headers, body = _response(origin, f"{prefix}/fault/{code}?private=synthetic")
    assert status == code
    assert "Service temporarily unavailable" in body
    assert "COYOT3" in body
    assert "synthetic upstream" not in body
    assert "private=synthetic" not in body
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert "max-age=31536000" in headers["Strict-Transport-Security"]


def test_connection_failure_and_stripped_prefix_use_local_error_page(error_proxy):
    """Render a real refused upstream connection and the supported outer-proxy prefix path."""
    origin, prefix = error_proxy
    status, _, body = _response(origin, f"{prefix}/docs-site/")
    assert status == 502
    assert "Service temporarily unavailable" in body
    if prefix:
        status, _, body = _response(origin, "/fault/503", headers={"X-Forwarded-Prefix": prefix})
        assert status == 503
        assert "Service temporarily unavailable" in body
        status, _, body = _response(origin, prefix)
        assert status == 503
        assert "Service temporarily unavailable" in body


def test_api_and_non_server_errors_pass_through(error_proxy):
    """Keep API JSON, frontend authorization failures and missing pages unchanged."""
    origin, prefix = error_proxy
    status, headers, body = _response(origin, f"{prefix}/api/fault")
    assert status == 503
    assert headers["Content-Type"] == "application/json"
    assert json.loads(body) == {"detail": "synthetic API error"}
    assert "no-store" != headers.get("Cache-Control")
    for code in [401, 403, 404]:
        status, _, body = _response(origin, f"{prefix}/fault/{code}")
        assert status == code
        assert body == "synthetic upstream"
    status, _, body = _response(origin, "/_coyote3_unavailable.html")
    assert status == 404
    assert "COYOT3" not in body


def test_error_page_handles_head_and_post_without_redirecting_browser(error_proxy):
    """Keep method-specific error responses at the original URL and preserve the status."""
    origin, prefix = error_proxy
    status, _, body = _response(origin, f"{prefix}/fault/504", method="HEAD")
    assert status == 504
    assert body == ""
    status, headers, body = _response(origin, f"{prefix}/fault/500", method="POST")
    assert status == 500
    assert headers.get("Location") is None
    assert "Service temporarily unavailable" in body
