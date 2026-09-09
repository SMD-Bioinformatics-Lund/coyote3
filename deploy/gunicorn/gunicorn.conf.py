"""Gunicorn hooks for deployments that still run through Gunicorn."""


def when_ready(server):
    """Log the Gunicorn readiness marker through the server logger.

    Args:
        server: Gunicorn server exposing the logger used for the informational message.

    Notes:
        Does not configure application logging; runtime setup owns that configuration.
    """
    server.log.info("coyote3 gunicorn ready")


def post_worker_stop(worker, worker_pid, exit_code) -> None:
    """Accept worker-stop callback arguments without performing cleanup.

    Args:
        worker: Stopped worker object; ignored.
        worker_pid: Process ID of the stopped worker; ignored.
        exit_code: Worker process exit status; ignored.
    """
    _ = (worker, worker_pid, exit_code)
