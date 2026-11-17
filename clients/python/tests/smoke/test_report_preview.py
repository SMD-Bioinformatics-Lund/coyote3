"""Fast authenticated report-preview transport contract without a server."""

import httpx

from coyote_pyclient import CoyoteClient


def test_temporary_report_returns_typed_downloads_without_a_save_request():
    """Trial rendering uses one read and retains HTML and PDF from the same response."""
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/session"):
            return httpx.Response(200, json={"user": {"username": "synthetic"}})
        return httpx.Response(
            200,
            json={
                "html": "<html><style>body{color:black}</style></html>",
                "pdf_base64": "JVBERi0xLjQ=",
                "filename": "coyote4_dna_report_trial",
                "snapshot_count": 3,
            },
        )

    with CoyoteClient("https://example.test", transport=httpx.MockTransport(respond)) as client:
        client.login_with_token("synthetic-token")
        requests.clear()
        trial = client.samples.ref("SYNTHETIC_TRIAL").reports.preview_bundle("dna")
    assert trial.snapshot_count == 3
    assert trial.pdf_base64 == "JVBERi0xLjQ="
    assert "<style>" in trial.html
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/api/v1/samples/SYNTHETIC_TRIAL/reports/dna/preview/bundle"
