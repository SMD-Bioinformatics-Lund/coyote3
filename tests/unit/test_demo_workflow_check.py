"""The release smoke check uses the current sample stream and revokes its session."""

import httpx
import pytest
from coyote3_client import CoyoteClient

from scripts.quality.check_demo_workflow import check_demo_workflow


@pytest.mark.parametrize("ready", [True, False])
def test_smoke_reads_current_contract_through_proxy_and_logs_out(ready):
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/auth/sessions"):
            return httpx.Response(
                200,
                json={"user": {"username": "synthetic"}},
                headers={"set-cookie": "coyote3_api_session=synthetic-token; HttpOnly; Secure"},
            )
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(
            200,
            json={
                "live_samples": [
                    {
                        "name": "DEMO_STARTER_DNA_SYNTHETIC",
                        "ingest_status": "ready" if ready else "failed",
                    }
                ],
                "live_page": 1,
                "live_per_page": 100,
                "live_total": 1,
                "has_next_live": False,
            },
        )

    with CoyoteClient(
        "https://synthetic.invalid/proxy", transport=httpx.MockTransport(respond)
    ) as client:
        if ready:
            assert (
                check_demo_workflow(client, username="synthetic", password="synthetic-password")
                == 1
            )
        else:
            with pytest.raises(RuntimeError, match="No ready"):
                check_demo_workflow(client, username="synthetic", password="synthetic-password")
        assert client.session_token is None
    assert requests[1].url.path == "/proxy/api/v1/samples"
    assert requests[1].headers["authorization"] == "Bearer synthetic-token"
    assert requests[-1].method == "DELETE"
