"""Gunicorn hooks for deployments that still run through Gunicorn."""


def when_ready(server):
    """Log a minimal readiness marker; app logging is configured by runtime setup."""
    server.log.info("coyote3 gunicorn ready")


def post_worker_stop(worker, worker_pid, exit_code) -> None:
    """Keep the hook for Gunicorn deployments."""
    _ = (worker, worker_pid, exit_code)
