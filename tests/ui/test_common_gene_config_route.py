"""Regression tests for the shared gene configuration route."""

from __future__ import annotations

import json

import coyote
from coyote import init_app


def test_sample_genelists_route_accepts_plain_json_payload(monkeypatch):
    """The config view should accept the plain JSON payload posted by the report page."""
    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)

    app = init_app(testing=True)
    app.config.update(WTF_CSRF_ENABLED=False)
    client = app.test_client()

    response = client.post(
        "/sample/s1/reports/config",
        data={
            "report_genelists": json.dumps({"Panel": ["TP53"]}),
            "panel_doc": json.dumps(
                {
                    "_id": "69d527e98867919eba89e90c",
                    "assay_name": "assay_1",
                    "name": "Panel doc",
                    "covered_genes": ["TP53", "NPM1"],
                }
            ),
            "report_sample_filters": json.dumps(
                {"genelists": ["Baseline"], "adhoc_genes": "Focus genes"}
            ),
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Focus genes" in body
    assert "Baseline" in body
    assert "assay_1" in body
    assert "69d527e98867919eba89e90c" not in body
