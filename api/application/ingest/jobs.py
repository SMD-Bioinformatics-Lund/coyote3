"""Durable job submission independent of transient broker availability."""

import logging

logger = logging.getLogger(__name__)


def submit_ingest_job(repository, publish, *, submitted_by, **submission):
    """Persist acceptance before notifying the worker; beat recovers broker failures."""
    job_id = repository.submit(submitted_by=submitted_by, **submission)
    try:
        publish(job_id)
    except Exception:
        logger.exception("Ingest job persisted; broker notification deferred")
    return job_id


def job_status_payload(job):
    """Expose status without exposing the staged payload, paths, or lease token."""
    state = job["state"]
    ready = state in {"succeeded", "failed"}
    payload = {
        "status": "ok",
        "task_id": str(job["_id"]),
        "state": {
            "pending": "PENDING",
            "running": "STARTED",
            "succeeded": "SUCCESS",
            "failed": "FAILURE",
        }[state],
        "ready": ready,
        "successful": state == "succeeded" if ready else None,
    }
    if state == "succeeded":
        payload["result"] = job.get("result")
    elif state == "failed":
        payload["error"] = job.get("error")
    return payload
