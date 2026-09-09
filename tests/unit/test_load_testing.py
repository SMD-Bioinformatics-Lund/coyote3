"""Exercise load-suite safety without importing Locust, gevent, or application code."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location(
    "load_support", Path(__file__).parents[1] / "load" / "support.py"
)
support = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(support)


@pytest.fixture
def inputs(tmp_path):
    """Provide separate synthetic configuration, credentials, and fixture files."""
    source = Path(__file__).parents[1] / "load"
    cfg = json.loads((source / "config.example.json").read_text())
    fixtures = json.loads((source / "fixtures.example.json").read_text())
    account = {"username": "synthetic", "password": "unit-only", "provider": "local"}
    return tmp_path, cfg, fixtures, account


def settings(inputs):
    """Write isolated input files and return validated settings."""
    path, cfg, fixtures, account = inputs
    (path / "config.json").write_text(json.dumps(cfg))
    (path / "fixtures.example.json").write_text(json.dumps(fixtures))
    (path / "credentials.json").write_text(json.dumps({"accounts": [account]}))
    return support.load_settings(str(path / "config.json"), str(path / "credentials.json"))


class Response:
    """Emulate a Locust catch-response context without network dependencies."""

    def __init__(self, body, status=200):
        """Store canned response data and independent success/failure spies."""
        self.body, self.status_code = body, status
        self.failure, self.success = Mock(), Mock()

    def __enter__(self):
        """Return this response context."""
        return self

    def __exit__(self, *args):
        """Leave errors visible to the caller."""
        return False

    def json(self):
        """Return canned JSON or simulate a JSON decoding failure."""
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def runner(cfg, responses):
    """Bind canned responses to a runner and return it with its request spy."""
    client = Mock()
    client.request.side_effect = responses
    return support.WorkflowRunner(client, cfg, cfg["accounts"][0], Mock(), sleep=Mock()), client


def about(cfg):
    """Return metadata matching explicit pins."""
    return {
        "application": {"environment": cfg["environment"], "script_name": "/coyote3"},
        "databases": cfg["databases"].copy(),
    }


def test_defaults_and_ca(inputs):
    """Keep TLS verification enabled and load CA paths relative to configuration."""
    cfg = settings(inputs)
    assert cfg["verify"] is True
    assert cfg["accounts"][0]["workflows"] == ["browsing", "findings", "dashboard"]
    (inputs[0] / "ca.pem").write_text("synthetic CA fixture")
    inputs[1]["ca_bundle"] = "ca.pem"
    assert settings(inputs)["verify"] == str(inputs[0] / "ca.pem")


@pytest.mark.parametrize(
    "target",
    [
        "https://user:password@example.org",
        "https://example.org?x=1",
        "https://example.org#x",
        "https://example.org?",
        "https://example.org#",
        "//example.org",
        "ftp://example.org",
        "https://example.org/a/../b",
        "https://example.org/%2f",
        "https://example.org\\evil",
        "https://example.org:invalid",
        "https://example.org\n",
        "https://@example.org",
    ],
)
def test_reject_target(inputs, target):
    """Reject redirects-by-construction, credentials, ambiguous paths, and unsupported schemes."""
    inputs[1]["target_url"] = target
    with pytest.raises(support.LoadError):
        settings(inputs)


@pytest.mark.parametrize(
    "key,value",
    [
        ("environment", "production"),
        ("environment", "unknown"),
        ("synthetic_data", False),
        ("external_lookups_disabled", "true"),
        ("databases", {"primary": "synthetic"}),
        ("allow_writes", "true"),
        ("request_timeout_seconds", 0),
        ("poll_timeout_seconds", float("inf")),
        ("max_poll_attempts", 1.5),
        ("think_time_seconds", [3, 1]),
        ("think_time_seconds", [0, 0]),
        ("verify", False),
        ("ca_bundle", False),
    ],
)
def test_reject_unsafe_config(inputs, key, value):
    """Fail configuration validation rather than silently applying unsafe defaults."""
    inputs[1][key] = value
    with pytest.raises(support.LoadError):
        settings(inputs)


@pytest.mark.parametrize(
    "workflows", [[], ["unknown"], ["comments"], ["ingest"], ["genes", "genes"]]
)
def test_reject_workflows(inputs, workflows):
    """Do not admit empty, unknown, duplicate, or unauthorized write personas."""
    inputs[3]["workflows"] = workflows
    with pytest.raises(support.LoadError):
        settings(inputs)


def test_reject_ldap_and_missing_declarations(inputs):
    """Restrict identities to local accounts and require both declarations."""
    inputs[3]["provider"] = "ldap"
    with pytest.raises(support.LoadError, match="local accounts"):
        settings(inputs)
    inputs[3]["provider"] = "local"
    del inputs[1]["synthetic_data"]
    with pytest.raises(support.LoadError):
        settings(inputs)


@pytest.mark.parametrize("field", ["samples", "gene_symbols", "rule_tests"])
def test_reject_empty_fixtures(inputs, field):
    """Every explicitly selected workflow must have its required manifest inputs."""
    inputs[3]["workflows"] = ["findings", "genes", "rule_testing"]
    inputs[2][field] = []
    with pytest.raises(support.LoadError):
        settings(inputs)


@pytest.mark.parametrize("value", ["", ".", "..", "a/b", "a\\b", "a%2fb", "a?b", "a#b", "a\nb"])
def test_path_injection(value):
    """Reject identifiers capable of changing path or query semantics."""
    with pytest.raises(support.LoadError):
        support.segment(value)


def test_quotes_identifier():
    """Encode punctuation while retaining a single path segment."""
    assert support.segment("chr7:140453136:A:T") == "chr7%3A140453136%3AA%3AT"


@pytest.mark.parametrize(
    "body",
    [
        {"error": "sensitive"},
        {"status": "error"},
        {"status": 403},
        {"status": "429"},
        {"success": False},
        {"detail": {"error": "sensitive"}},
        [],
        None,
    ],
)
def test_http_200_error_envelopes(body):
    """Reject error envelopes without including response content in exceptions."""
    with pytest.raises(support.LoadError) as exc:
        support.envelope(body)
    assert "sensitive" not in str(exc.value)


@pytest.mark.parametrize(
    "field", ["environment", "primary", "identity", "bam_service", "script_name"]
)
def test_preflight_blocks_before_login(inputs, field):
    """Never send credentials to a deployment whose metadata disagrees with pins."""
    cfg = settings(inputs)
    body = about(cfg)
    target = body["application"] if field in {"environment", "script_name"} else body["databases"]
    target[field] = "production"
    response = Response(body)
    flow, client = runner(cfg, [response])
    with pytest.raises(support.LoadError):
        flow.start()
    assert client.request.call_count == 1
    assert client.request.call_args.kwargs["headers"] == {}
    response.failure.assert_called_once()


def test_login_cookie_csrf_and_fixed_routes(inputs):
    """Keep prefix, templated metrics, TLS, redirect policy, and session lifecycle intact."""
    cfg = settings(inputs)
    flow, client = runner(
        cfg,
        [
            Response(about(cfg)),
            Response({"csrf_token": "secret", "user": {}}),
            Response({"sample": {}, "variants": []}),
            Response({"sample": {}, "variant": {}}),
            Response({"status": "ok"}),
        ],
    )
    flow.start()
    flow.run("findings")
    flow.stop()
    flow.stop()
    assert client.request.call_count == 5
    for call in client.request.call_args_list:
        assert call.args[1].startswith(cfg["target_url"] + "/api/v1/")
        assert call.kwargs["allow_redirects"] is False
        assert call.kwargs["verify"] is True
        assert call.kwargs["timeout"] == 10
        assert "demo_" not in call.kwargs["name"]
    assert client.request.call_args.kwargs["headers"] == {"X-CSRF-Token": "secret"}


@pytest.mark.parametrize("status", [0, 301, 302, 307, 308, 401, 403, 429, 500])
def test_http_failures_are_sanitized(inputs, status):
    """Retain visible HTTP failures, including rate limits, with no retries or body leakage."""
    response = Response({"error": "token private-id"}, status)
    flow, client = runner(settings(inputs), [response])
    with pytest.raises(support.LoadError, match="unexpected HTTP status"):
        flow.request("dashboard")
    response.failure.assert_called_once_with(f"unexpected HTTP status {status}")
    assert client.request.call_count == 1


def test_ingest_success_and_uniqueness(inputs):
    """Record terminal success separately and use unique canonical create-only sample input."""
    inputs[1]["allow_writes"] = True
    inputs[3]["workflows"] = ["ingest"]
    cfg = settings(inputs)
    submission = {"status": "accepted", "task_id": "synthetic-task"}
    pending = {"status": "ok", "task_id": "synthetic-task", "state": "PENDING", "ready": False}
    success = {
        "status": "ok",
        "task_id": "synthetic-task",
        "state": "SUCCESS",
        "ready": True,
        "successful": True,
        "result": {"status": "ok", "sample_id": "synthetic-sample"},
    }
    flow, client = runner(cfg, [Response(submission, 202), Response(pending), Response(success)])
    flow.run("ingest")
    payload = client.request.call_args_list[0].kwargs["json"]
    assert payload["sample"]["name"].startswith("load_sample_")
    assert payload["sample"]["case_id"].startswith("load_case_")
    assert payload["update_existing"] is payload["increment"] is False
    assert cfg["fixtures"]["ingest_sample_template"]["name"] == "load_sample"
    flow.emit.assert_called_once()
    assert flow.emit.call_args.kwargs["exception"] is None
    assert flow.emit.call_args.kwargs["name"] == "ingest/terminal"


@pytest.mark.parametrize(
    "result",
    [
        {"state": "FAILURE", "ready": True, "successful": False, "error": "private"},
        {"state": "SUCCESS", "ready": True, "successful": True, "result": {"status": "error"}},
        {"state": "SUCCESS", "ready": True, "successful": False},
        {"state": "SUCCESS", "ready": False},
    ],
)
def test_task_failures(result):
    """Celery completion alone cannot turn a failed domain result into success."""
    with pytest.raises(support.LoadError):
        support.check_task({"status": "ok", "task_id": "task", **result}, "task")


def test_poll_budget_and_bad_task_id(inputs):
    """Bound pending polls and prohibit response-supplied path injection."""
    inputs[1].update(allow_writes=True, max_poll_attempts=1)
    inputs[3]["workflows"] = ["ingest"]
    cfg = settings(inputs)
    for task_id in ["task", "../private"]:
        flow, client = runner(
            cfg,
            [
                Response({"status": "accepted", "task_id": task_id}, 202),
                Response({"status": "ok", "task_id": "task", "state": "PENDING", "ready": False}),
            ],
        )
        with pytest.raises(support.LoadError):
            flow.run("ingest")
        assert client.request.call_count == (2 if task_id == "task" else 1)
        assert isinstance(flow.emit.call_args.kwargs["exception"], support.LoadError)


def test_ingest_template_rejects_files_and_unknown_fields(inputs):
    """Disallow server filesystem ingestion and undocumented template fields."""
    for key, value in [
        ("files", {"vcf": {"path": "/private"}}),
        ("yaml_content", "private"),
        ("sample_name", "old-contract"),
    ]:
        template = inputs[2]["ingest_sample_template"].copy()
        inputs[2]["ingest_sample_template"][key] = value
        with pytest.raises(support.LoadError):
            settings(inputs)
        inputs[2]["ingest_sample_template"] = template


def test_production_clinical_profile_is_not_runtime(inputs):
    """Allow synthetic samples in a production clinical profile on a pinned test deployment."""
    inputs[2]["ingest_sample_template"]["environment"] = "production"
    assert settings(inputs)["environment"] == "test"


def test_report_preview_and_rule_pairs(inputs):
    """Use explicit report analytes and compatible rule/sample pairs without persistence."""
    inputs[3]["workflows"] = ["report_preview", "rule_testing"]
    inputs[2]["rule_tests"] = [{"sample_id": "paired_sample", "rule_version_id": "paired_rule"}]
    cfg = settings(inputs)
    flow, client = runner(
        cfg,
        [
            Response({"sample": {}, "meta": {}, "report": {"html": "<p>Synthetic</p>"}}),
            Response({"sample": {}, "rule_set": {}, "evaluation": {}, "persisted": False}),
        ],
    )
    flow.run("report_preview")
    flow.run("rule_testing")
    preview = client.request.call_args_list[0]
    assert preview.args[0] == "GET"
    assert preview.args[1].endswith("/reports/dna/preview")
    assert preview.kwargs["params"] == {"save": "false", "include_snapshot": "false"}
    assert client.request.call_args.args[1].endswith(
        "/versions/paired_rule/test-samples/paired_sample/preview"
    )


@pytest.mark.parametrize(
    "body",
    [
        {"sample": {}, "meta": {}, "report": {"html": ""}},
        {"sample": {}, "meta": {}, "report": {}},
    ],
)
def test_empty_report_is_failure(inputs, body):
    """A report preview must contain rendered HTML, not an empty success envelope."""
    flow, _ = runner(settings(inputs), [Response(body)])
    with pytest.raises(support.LoadError, match="empty report preview"):
        flow.request("report_preview", ids={"sample_id": "sample", "report_type": "dna"})


def test_request_event_metadata_is_sanitized(inputs):
    """Prevent event consumers from seeing raw responses, credential bodies, or identifier URLs."""
    response = Response({"error": "private server error"}, 429)
    response.request_meta = {
        "response": response,
        "url": "https://private/id",
        "context": {"x": "private"},
    }
    flow, _ = runner(settings(inputs), [response])
    with pytest.raises(support.LoadError, match="unexpected HTTP status 429"):
        flow.request("dashboard")
    assert response.request_meta == {
        "response": None,
        "url": "/api/v1/dashboard/metrics/samples",
        "context": {},
    }


def test_malformed_json_and_task_correlation(inputs):
    """Sanitize decoder errors and reject mismatched terminal task identities."""
    response = Response(ValueError("private response"))
    flow, _ = runner(settings(inputs), [response])
    with pytest.raises(support.LoadError, match="invalid JSON envelope"):
        flow.request("dashboard")
    response.failure.assert_called_once_with("invalid JSON envelope")
    with pytest.raises(support.LoadError, match="task correlation mismatch"):
        support.check_task({"task_id": "different"}, "expected")


def test_preview_requires_report_type(inputs):
    """Reject a selected preview workflow whose samples have no explicit analyte."""
    inputs[3]["workflows"] = ["report_preview"]
    del inputs[2]["samples"][0]["report_type"]
    with pytest.raises(support.LoadError, match="report type required"):
        settings(inputs)


def test_example_ingest_matches_api_contract(inputs):
    """Keep the shipped template aligned with the actual canonical ingest contract."""
    from api.contracts.internal import InternalIngestSampleBundleRequest

    sample = inputs[2]["ingest_sample_template"]
    payload = InternalIngestSampleBundleRequest.model_validate(
        {"sample": sample, "update_existing": False, "increment": False}
    )
    assert payload.sample.name == "load_sample"
    assert payload.sample.environment == "testing"
    assert payload.sample.files["biomarkers"].path == "/load/synthetic/biomarkers.json"
    assert payload.yaml_content is None
    assert payload.update_existing is payload.increment is False


def test_synthetic_biomarker_matches_api_contract():
    """Check shipped biomarker rows with the sample identity supplied by ingestion."""
    from api.contracts.schemas.dna import BiomarkersDoc

    path = Path(__file__).parents[1] / "load" / "synthetic" / "biomarkers.json"
    rows = json.loads(path.read_text())
    assert rows
    for row in rows:
        parsed = BiomarkersDoc.model_validate({**row, "SAMPLE_ID": "synthetic-sample"})
        assert parsed.name == "synthetic_load_biomarker"
