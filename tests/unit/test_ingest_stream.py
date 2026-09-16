"""Ingest streams deliver isolated live logs and preserve terminal outcomes."""

import asyncio
import json
import logging
from threading import Event, Thread

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from api.interfaces.http.operations.ingest_stream import stream_ingest


def test_logs_arrive_before_completion_and_exclude_other_threads(caplog):
    caplog.set_level(logging.INFO)
    release = Event()
    logger = logging.getLogger("api.application.ingest.service")

    def operation():
        """Wait until the client has received the initial progress event."""
        other = Thread(target=lambda: logger.info("unrelated submission"))
        other.start()
        other.join()
        logger.info("Parsing synthetic VCF")
        assert release.wait(5)
        return {"status": "ok", "sample_id": "synthetic"}

    async def consume():
        """Release processing only after observing its initial log."""
        received = []
        async for line in stream_ingest(operation).body_iterator:
            event = json.loads(line)
            received.append(event)
            if event["event"] == "log":
                release.set()
        return received

    try:
        events = asyncio.run(consume())
    finally:
        release.set()
    assert [e["event"] for e in events] == ["log", "result"]
    assert events[0]["message"] == "Parsing synthetic VCF"
    assert events[-1]["data"]["status"] == "ok"


@pytest.mark.parametrize("failure", ["validation", "http", "unexpected", "response"])
def test_terminal_errors_and_acknowledgements(failure):
    def operation():
        """Represent the possible upload route outcomes."""
        if failure == "validation":
            return {"status": "failed", "message": "Invalid input"}
        if failure == "http":
            raise HTTPException(403, "Forbidden")
        if failure == "unexpected":
            raise RuntimeError("synthetic failure")
        return JSONResponse({"error": "synthetic failure", "request_id": "trace"}, status_code=500)

    async def consume():
        """Collect the stream's terminal event."""
        return [json.loads(line) async for line in stream_ingest(operation).body_iterator]

    terminal = asyncio.run(consume())[-1]
    if failure == "validation":
        assert terminal == {
            "event": "result",
            "data": {"status": "failed", "message": "Invalid input"},
        }
    else:
        assert terminal["event"] == "error"
        assert terminal["status_code"] == (403 if failure == "http" else 500)


def test_stream_keeps_uploaded_file_open_until_consumed():
    """Exercise FastAPI's upload lifetime across a streaming response."""
    from fastapi import FastAPI, UploadFile
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.post("/upload")
    def upload(file: UploadFile):
        """Read the upload inside the deferred operation."""
        return stream_ingest(lambda: {"text": file.file.read().decode()})

    with TestClient(app) as client:
        response = client.post("/upload", files={"file": ("sample.yaml", b"synthetic")})
    assert response.headers["x-accel-buffering"] == "no"
    assert response.json() == {"event": "result", "data": {"text": "synthetic"}}
