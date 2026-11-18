"""Redis TLS overlays preserve storage and validate server certificates."""

import json
import os
import shutil
import ssl
import subprocess
from pathlib import Path

import pytest
from celery import Celery
from redis.connection import SSLConnection, parse_url

ROOT = Path(__file__).resolve().parents[2]


def test_redis_tls_overlay_uses_verified_transport_without_network_changes():
    """Render Compose without a daemon and inspect every Redis client endpoint."""
    if not shutil.which("docker"):
        pytest.skip("Docker Compose CLI required; no daemon is used")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "deploy/env/example.env",
            "-f",
            "deploy/compose/docker-compose.yml",
            "-f",
            "deploy/compose/docker-compose.redis-tls.yml",
            "-f",
            "deploy/compose/docker-compose.redis.yml",
            "-f",
            "deploy/compose/docker-compose.redis-tls-server.yml",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "COYOTE4_VERSION": "tls-test",
            "COYOTE4_IMAGE_TAG": "tls-test",
            "COYOTE4_REDIS_TLS_DIR": "/synthetic/redis-certificates",
            "COYOTE4_REDIS_VOLUME": "synthetic-redis-data",
            "REDIS_PASSWORD": "synthetic_redis_password",
            **{
                key: f"rediss://:synthetic_redis_password@redis:6379/{number}?ssl_cert_reqs=required&ssl_ca_certs=/run/redis-tls/ca.crt&ssl_check_hostname=true"
                for number, key in enumerate(
                    ("CACHE_REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")
                )
            },
        },
    )
    rendered = json.loads(result.stdout)
    assert rendered["networks"]["app"]["external"] is True
    for name in ("api", "worker", "maintenance-worker", "beat", "monitor"):
        service = rendered["services"][name]
        for key in ("CACHE_REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
            connection = parse_url(service["environment"][key])
            assert connection["connection_class"] is SSLConnection
            assert connection["ssl_cert_reqs"] == "required"
            assert connection["ssl_check_hostname"] is True
            assert connection["ssl_ca_certs"] == "/run/redis-tls/ca.crt"
        with Celery(
            "tls-config-test",
            broker=service["environment"]["CELERY_BROKER_URL"],
            backend=service["environment"]["CELERY_RESULT_BACKEND"],
        ) as app:
            broker = app.connection_for_write()
            assert broker.ssl["ssl_cert_reqs"] == ssl.CERT_REQUIRED
            assert broker.ssl["ssl_check_hostname"] is True
            assert app.backend.connparams["ssl_cert_reqs"] == ssl.CERT_REQUIRED
            assert app.backend.connparams["ssl_check_hostname"] is True
        mounts = service["volumes"]
        assert any(mount["target"] == "/data" for mount in mounts)
        assert any(
            mount["target"] == "/run/redis-tls/ca.crt" and mount["read_only"] for mount in mounts
        )
        assert not any(mount["target"].endswith("server.key") for mount in mounts)
    redis = rendered["services"]["redis"]
    assert "--port 0 --tls-port 6379" in redis["command"][-1]
    assert "--requirepass" in redis["command"][-1]
    assert "--tls" in redis["healthcheck"]["test"][-1]
    assert any(mount["target"] == "/data" for mount in redis["volumes"])
    assert redis["ports"][0]["host_ip"] == "127.0.0.1"
