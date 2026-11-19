"""Runtime startup fails closed and remains retryable in every host environment."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote_api.app import lifecycle


@pytest.fixture(autouse=True)
def uninitialized_runtime(monkeypatch):
    """Isolate completion state without replacing the initializer under test."""
    monkeypatch.setattr(lifecycle, "_runtime_initialized", False)
    monkeypatch.setattr(lifecycle, "_runtime_context", None)
    monkeypatch.setattr(lifecycle, "_runtime_mode", None)
    monkeypatch.setattr(lifecycle, "_lifespan_owners", 0)
    monkeypatch.setattr(lifecycle, "_process_owner", False)


@pytest.mark.parametrize("testing", [False, True])
@pytest.mark.parametrize("pytest_environment", [False, True])
def test_failed_bootstrap_propagates_and_can_retry(monkeypatch, testing, pytest_environment):
    """Failed dependency creation cannot mark startup ready, including under pytest."""
    if pytest_environment:
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "synthetic-startup-test")
    else:
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    failure = RuntimeError("Synthetic dependency unavailable")
    runtime = object()
    create = Mock(side_effect=[failure, runtime])
    bind = Mock()
    monkeypatch.setattr(lifecycle, "create_runtime_context", create)
    monkeypatch.setattr(lifecycle, "bind_runtime_context", bind)

    with pytest.raises(RuntimeError) as raised:
        lifecycle.ensure_runtime_initialized(testing=testing, development=False)
    assert raised.value is failure
    assert not lifecycle._runtime_initialized
    bind.assert_not_called()

    lifecycle.ensure_runtime_initialized(testing=testing, development=False)
    lifecycle.ensure_runtime_initialized(testing=testing, development=False)
    assert lifecycle._runtime_initialized
    assert create.call_count == 2
    create.assert_called_with(testing=testing, development=False)
    bind.assert_called_once_with(runtime)


def test_failed_binding_does_not_mark_runtime_ready(monkeypatch):
    """A host-context binding failure must also propagate and permit another attempt."""
    runtimes = [Mock(), Mock()]
    create = Mock(side_effect=runtimes)
    bind = Mock(side_effect=[ValueError("Invalid synthetic runtime context"), None])
    monkeypatch.setattr(lifecycle, "create_runtime_context", create)
    monkeypatch.setattr(lifecycle, "bind_runtime_context", bind)

    with pytest.raises(ValueError, match="Invalid synthetic runtime context"):
        lifecycle.ensure_runtime_initialized(testing=False, development=False)
    assert not lifecycle._runtime_initialized
    runtimes[0].close.assert_called_once()

    lifecycle.ensure_runtime_initialized(testing=False, development=False)
    assert lifecycle._runtime_initialized
    assert create.call_count == bind.call_count == 2


@pytest.mark.asyncio
async def test_overlapping_applications_release_only_the_last_owner(monkeypatch):
    """Stopping one app must not close a runtime still serving another app."""
    runtime = Mock()
    monkeypatch.setattr(lifecycle, "create_runtime_context", Mock(return_value=runtime))
    monkeypatch.setattr(lifecycle, "bind_runtime_context", Mock())
    monkeypatch.setattr(lifecycle, "initialize_storage_directories", Mock())
    lifespan = lifecycle.create_lifespan(testing=True, development=False)
    first, second = [SimpleNamespace(state=SimpleNamespace()) for _ in range(2)]
    async with lifespan(first):
        async with lifespan(second):
            assert first.state.runtime is second.state.runtime is runtime
            lifecycle.ensure_runtime_initialized(testing=True, development=False)
        runtime.close.assert_not_called()
        assert second.state.runtime is None
    runtime.close.assert_called_once()
    assert first.state.runtime is None
    assert not lifecycle._runtime_initialized


@pytest.mark.asyncio
async def test_failed_directory_setup_releases_resources_and_allows_recreation(monkeypatch):
    """Post-bootstrap failure must neither serve requests nor poison the next startup."""
    runtimes = [Mock(), Mock()]
    monkeypatch.setattr(lifecycle, "create_runtime_context", Mock(side_effect=runtimes))
    monkeypatch.setattr(lifecycle, "bind_runtime_context", Mock())
    monkeypatch.setattr(
        lifecycle, "initialize_storage_directories", Mock(side_effect=[OSError("storage"), None])
    )
    lifespan = lifecycle.create_lifespan(testing=True, development=False)
    application = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(OSError, match="storage"):
        async with lifespan(application):
            pytest.fail("Started despite unavailable storage")
    runtimes[0].close.assert_called_once()
    async with lifespan(application):
        assert application.state.runtime is runtimes[1]
    runtimes[1].close.assert_called_once()


@pytest.mark.asyncio
async def test_incompatible_application_cannot_replace_active_runtime(monkeypatch):
    runtime = Mock()
    monkeypatch.setattr(lifecycle, "create_runtime_context", Mock(return_value=runtime))
    monkeypatch.setattr(lifecycle, "bind_runtime_context", Mock())
    monkeypatch.setattr(lifecycle, "initialize_storage_directories", Mock())
    application = SimpleNamespace(state=SimpleNamespace())
    async with lifecycle.create_lifespan(testing=True, development=False)(application):
        with pytest.raises(RuntimeError, match="same mode"):
            async with lifecycle.create_lifespan(testing=False, development=False)(
                SimpleNamespace(state=SimpleNamespace())
            ):
                pytest.fail("Mixed configurations must not share process globals")
        runtime.close.assert_not_called()
    runtime.close.assert_called_once()


@pytest.mark.asyncio
async def test_worker_owned_runtime_survives_asgi_shutdown(monkeypatch):
    runtime = Mock()
    monkeypatch.setattr(lifecycle, "create_runtime_context", Mock(return_value=runtime))
    monkeypatch.setattr(lifecycle, "bind_runtime_context", Mock())
    monkeypatch.setattr(lifecycle, "initialize_storage_directories", Mock())
    lifecycle.ensure_runtime_initialized(testing=True, development=False)
    async with lifecycle.create_lifespan(testing=True, development=False)(
        SimpleNamespace(state=SimpleNamespace())
    ):
        pass
    runtime.close.assert_not_called()
    lifecycle.shutdown_runtime()
    lifecycle.shutdown_runtime()
    runtime.close.assert_called_once()


def test_concurrent_startup_creates_and_binds_one_runtime(monkeypatch):
    """A caller waiting for bootstrap must reuse the successfully bound runtime."""
    creation_started = Event()
    permit_completion = Event()
    second_started = Event()
    runtime = object()

    def create(**kwargs):
        creation_started.set()
        assert permit_completion.wait(timeout=5), "Synthetic bootstrap was not released"
        return runtime

    create_mock = Mock(side_effect=create)
    bind = Mock()
    monkeypatch.setattr(lifecycle, "create_runtime_context", create_mock)
    monkeypatch.setattr(lifecycle, "bind_runtime_context", bind)

    def initialize_second():
        second_started.set()
        lifecycle.ensure_runtime_initialized(testing=False, development=False)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            lifecycle.ensure_runtime_initialized, testing=False, development=False
        )
        try:
            assert creation_started.wait(timeout=5)
            second = executor.submit(initialize_second)
            assert second_started.wait(timeout=5)
            assert not first.done()
            assert not second.done()
        finally:
            permit_completion.set()
        first.result(timeout=5)
        second.result(timeout=5)
    create_mock.assert_called_once_with(testing=False, development=False)
    bind.assert_called_once_with(runtime)


@pytest.mark.asyncio
async def test_failed_lifespan_never_starts_serving(monkeypatch):
    """The actual lifespan cannot yield after a dependency initialization failure."""
    create = Mock(side_effect=RuntimeError("Synthetic startup failure"))
    directories = Mock()
    monkeypatch.setattr(lifecycle, "create_runtime_context", create)
    monkeypatch.setattr(lifecycle, "initialize_storage_directories", directories)
    lifespan = lifecycle.create_lifespan(testing=False, development=False)

    with pytest.raises(RuntimeError, match="Synthetic startup failure"):
        async with lifespan(None):
            pytest.fail("Application started serving after failed initialization")
    directories.assert_not_called()
    assert not lifecycle._runtime_initialized


def test_normal_process_rejects_missing_production_secrets_before_startup(tmp_path):
    """A fresh non-pytest process rejects missing configuration without opening services."""
    environment = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT") if key in os.environ}
    environment.update(
        COYOTE4_RUNTIME_ROOT=str(tmp_path),
        ENV_NAME="production",
        TESTING="0",
        DEVELOPMENT="0",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from coyote_api.app.lifecycle import ensure_runtime_initialized; "
            "ensure_runtime_initialized(testing=False, development=False)",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr
    assert "RuntimeError" in result.stderr
    assert "Skipping runtime DB bootstrap" not in result.stderr
