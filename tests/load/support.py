"""Dependency-free configuration, response checks, and fixed HTTP workflows."""

from __future__ import annotations

import copy
import json
import math
import random
import re
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urlsplit

NONPRODUCTION = {"development", "dev", "testing", "test", "staging", "local"}
WEIGHTS = {
    "browsing": 5,
    "findings": 5,
    "dashboard": 2,
    "genes": 2,
    "reports": 1,
    "report_preview": 1,
    "rule_testing": 1,
    "comments": 1,
    "ingest": 1,
}
DEFAULT_WORKFLOWS = ["browsing", "findings", "dashboard"]
INGEST_FILES = {"biomarkers": {"path": "/load/synthetic/biomarkers.json"}}
ROUTES = {
    "about": ("GET", "/api/v1/public/about", 200, {"application": dict, "databases": dict}),
    "login": ("POST", "/api/v1/auth/sessions", 200, {"csrf_token": str, "user": dict}),
    "logout": ("DELETE", "/api/v1/auth/sessions/current", 200, {"status": str}),
    "browsing": ("GET", "/api/v1/samples", 200, {"live_samples": list, "done_samples": list}),
    "findings": (
        "GET",
        "/api/v1/samples/{sample_id}/small-variants",
        200,
        {"sample": dict, "variants": list},
    ),
    "finding": (
        "GET",
        "/api/v1/samples/{sample_id}/small-variants/{finding_id}",
        200,
        {"sample": dict, "variant": dict},
    ),
    "dashboard": ("GET", "/api/v1/dashboard/metrics/samples", 200, {"metric_meta": dict}),
    "genes": ("GET", "/api/v1/common/gene/{gene_id}/info", 200, {"gene": dict}),
    "reports": ("GET", "/api/v1/reports", 200, {"reports": list, "total": int}),
    "report_preview": (
        "GET",
        "/api/v1/samples/{sample_id}/reports/{report_type}/preview",
        200,
        {"sample": dict, "meta": dict, "report": dict},
    ),
    "rule_testing": (
        "POST",
        "/api/v1/admin/clinical-rule-sets/versions/{rule_id}/test-samples/{sample_id}/preview",
        200,
        {"sample": dict, "rule_set": dict, "evaluation": dict, "persisted": bool},
    ),
    "comments": (
        "POST",
        "/api/v1/samples/{sample_id}/comments",
        201,
        {"status": str, "resource": str, "action": str},
    ),
    "ingest": (
        "POST",
        "/api/v1/internal/ingest/sample-bundle/async",
        202,
        {"status": str, "task_id": str},
    ),
    "poll": (
        "GET",
        "/api/v1/internal/tasks/{task_id}",
        200,
        {"status": str, "task_id": str, "state": str, "ready": bool},
    ),
}


class LoadError(ValueError):
    """Carry only stable, operator-safe failure messages."""


def require(condition: bool, message: str = "invalid configuration") -> None:
    """Reject a failed invariant without including input values.

    Args:
        condition: Whether the invariant holds.
        message: Constant sanitized explanation.

    Raises:
        LoadError: The invariant does not hold.
    """
    if not condition:
        raise LoadError(message)


def read_json(path: Path) -> dict:
    """Read a local JSON object without exposing its contents on failure.

    Args:
        path: Operator-controlled local JSON path.

    Returns:
        Decoded object.

    Raises:
        LoadError: File cannot be read or is not a JSON object.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise LoadError("cannot read JSON configuration") from None
    require(isinstance(value, dict))
    return value


def segment(value: str) -> str:
    """Validate and quote one identifier, never accepting path syntax.

    Args:
        value: Explicit fixture identifier or validated task identifier.

    Returns:
        Percent-encoded single path segment.

    Raises:
        LoadError: Identifier is empty, oversized, or contains path/control syntax.
    """
    require(isinstance(value, str) and 0 < len(value) <= 200, "invalid identifier")
    require(
        value not in {".", ".."} and not re.search(r"[/\\%?#\s\x00-\x1f\x7f]", value),
        "invalid identifier",
    )
    return quote(value, safe="")


def number(value: object, minimum: float, maximum: float) -> bool:
    """Check a finite bounded number, excluding booleans.

    Args:
        value: Candidate JSON value.
        minimum: Inclusive lower bound.
        maximum: Inclusive upper bound.

    Returns:
        Whether the value satisfies the bounds.
    """
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def load_settings(config_path: str, credentials_path: str) -> dict:
    """Validate all operator inputs before any HTTP or credential transmission.

    Args:
        config_path: Required local configuration filename.
        credentials_path: Separate required private account filename.

    Returns:
        Validated settings with loaded accounts and fixtures.

    Raises:
        LoadError: Configuration, account selection, or fixtures violate the contract.
    """
    require(bool(config_path) and bool(credentials_path), "required load paths missing")
    path = Path(config_path).resolve()
    require(path != Path(credentials_path).resolve(), "credentials must be separate")
    cfg = read_json(path)
    allowed = {
        "target_url",
        "environment",
        "databases",
        "synthetic_data",
        "external_lookups_disabled",
        "fixtures_file",
        "allow_writes",
        "ca_bundle",
        "request_timeout_seconds",
        "think_time_seconds",
        "poll_interval_seconds",
        "poll_timeout_seconds",
        "max_poll_attempts",
    }
    require(not (cfg.keys() - allowed), "unknown configuration key")
    require(
        cfg.get("synthetic_data") is True and cfg.get("external_lookups_disabled") is True,
        "explicit isolation declarations required",
    )
    require(
        isinstance(cfg.get("environment"), str) and cfg["environment"] in NONPRODUCTION,
        "nonproduction environment required",
    )
    target = cfg.get("target_url")
    require(isinstance(target, str), "invalid target URL")
    try:
        url = urlsplit(target)
        valid = (
            url.scheme in {"http", "https"}
            and bool(url.hostname)
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and "?" not in target
            and "#" not in target
            and "@" not in url.netloc
            and not re.search(r"[\s\\\x00-\x1f\x7f]", target)
        )
        _ = url.port
    except ValueError:
        raise LoadError("invalid target URL") from None
    require(valid, "invalid target URL")
    require(
        not url.path
        or url.path == "/"
        or all(re.fullmatch(r"[A-Za-z0-9_-]+", part) for part in url.path.strip("/").split("/")),
        "invalid SCRIPT_NAME",
    )
    cfg["target_url"] = target.rstrip("/")
    cfg["script_name"] = url.path.rstrip("/")
    dbs = cfg.get("databases")
    require(
        isinstance(dbs, dict) and set(dbs) == {"primary", "identity", "bam_service"},
        "exact database pins required",
    )
    require(
        all(isinstance(v, str) and v.strip() == v and v for v in dbs.values()),
        "exact database pins required",
    )
    require(type(cfg.get("allow_writes", False)) is bool)
    cfg.setdefault("allow_writes", False)
    for key, default, low, high in [
        ("request_timeout_seconds", 10, 0.1, 120),
        ("poll_interval_seconds", 1, 0.1, 30),
        ("poll_timeout_seconds", 60, 1, 600),
        ("max_poll_attempts", 60, 1, 600),
    ]:
        cfg.setdefault(key, default)
        require(number(cfg[key], low, high), "invalid timing budget")
    require(type(cfg["max_poll_attempts"]) is int)
    cfg.setdefault("think_time_seconds", [1, 3])
    think = cfg["think_time_seconds"]
    require(
        isinstance(think, list)
        and len(think) == 2
        and all(number(v, 0.1, 60) for v in think)
        and think[0] <= think[1],
        "invalid think time",
    )
    cfg["verify"] = True
    if "ca_bundle" in cfg:
        require(isinstance(cfg["ca_bundle"], str) and bool(cfg["ca_bundle"]), "invalid CA path")
        ca = path.parent / cfg["ca_bundle"]
        require(ca.is_file(), "CA bundle missing")
        cfg["verify"] = str(ca.resolve())
    require(isinstance(cfg.get("fixtures_file"), str) and bool(cfg["fixtures_file"]))
    fixture_path = (path.parent / cfg["fixtures_file"]).resolve()
    require(fixture_path != Path(credentials_path).resolve(), "credentials must be separate")
    fixtures = read_json(fixture_path)
    accounts_doc = read_json(Path(credentials_path))
    require(set(accounts_doc) == {"accounts"})
    accounts = accounts_doc["accounts"]
    require(isinstance(accounts, list) and bool(accounts), "accounts required")
    for account in accounts:
        require(
            isinstance(account, dict)
            and not (account.keys() - {"username", "password", "provider", "workflows"})
        )
        require(
            all(isinstance(account.get(k), str) and account[k] for k in ("username", "password")),
            "invalid credentials",
        )
        account.setdefault("provider", "local")
        require(account["provider"] == "local", "local accounts required")
        account.setdefault("workflows", DEFAULT_WORKFLOWS.copy())
        flows = account["workflows"]
        require(
            isinstance(flows, list)
            and bool(flows)
            and all(isinstance(f, str) and f in WEIGHTS for f in flows),
            "invalid workflows",
        )
        require(len(flows) == len(set(flows)), "duplicate workflows")
        require(
            cfg["allow_writes"] or not set(flows) & {"comments", "ingest"},
            "write workflows require allow_writes",
        )
    validate_fixtures(fixtures, {f for a in accounts for f in a["workflows"]})
    cfg.update(accounts=accounts, fixtures=fixtures)
    return cfg


def validate_fixtures(fixtures: dict, workflows: set[str]) -> None:
    """Require explicit resources for every selected workflow.

    Args:
        fixtures: Version-one synthetic resource manifest.
        workflows: Union of configured persona workflows.

    Raises:
        LoadError: Resources are missing or the ingest template is not supported canonical input.
    """
    require(type(fixtures.get("schema_version")) is int and fixtures["schema_version"] == 1)
    require(
        not fixtures.keys()
        - {
            "schema_version",
            "samples",
            "gene_symbols",
            "rule_tests",
            "ingest_sample_template",
        }
    )
    samples = fixtures.get("samples", [])
    require(isinstance(samples, list))
    if workflows & {"browsing", "findings", "comments", "report_preview"}:
        require(bool(samples), "sample fixtures required")
    for sample in samples:
        require(
            isinstance(sample, dict)
            and {"sample_id", "finding_ids"} <= sample.keys()
            and not sample.keys() - {"sample_id", "finding_ids", "report_type"}
        )
        segment(sample["sample_id"])
        if "report_preview" in workflows or "report_type" in sample:
            require(sample.get("report_type") in ("dna", "rna"), "report type required")
        require(isinstance(sample["finding_ids"], list))
        if "findings" in workflows:
            require(bool(sample["finding_ids"]), "finding fixtures required")
        for finding in sample["finding_ids"]:
            segment(finding)
    for key, flow in [("gene_symbols", "genes")]:
        values = fixtures.get(key, [])
        require(isinstance(values, list))
        require(flow not in workflows or bool(values), "workflow fixtures required")
        for value in values:
            segment(value)
    pairs = fixtures.get("rule_tests", [])
    require(isinstance(pairs, list))
    require("rule_testing" not in workflows or bool(pairs), "rule test pairs required")
    for pair in pairs:
        require(isinstance(pair, dict) and set(pair) == {"sample_id", "rule_version_id"})
        segment(pair["sample_id"])
        segment(pair["rule_version_id"])
    if "ingest" in workflows or "ingest_sample_template" in fixtures:
        sample = fixtures.get("ingest_sample_template")
        required = {
            "name",
            "asp_id",
            "environment",
            "case_id",
            "sample_no",
            "sequencing_scope",
            "omics_layer",
            "pipeline",
        }
        allowed = required | {
            "subpanel_id",
            "genome_build",
            "database_versions",
            "analysis_intents",
            "files",
        }
        require(
            isinstance(sample, dict) and required <= sample.keys() and not sample.keys() - allowed,
            "invalid ingest template",
        )
        require(
            all(isinstance(sample[k], str) and bool(sample[k]) for k in required - {"sample_no"}),
            "invalid ingest template",
        )
        require(
            sample["name"].startswith("load_") and sample["case_id"].startswith("load_"),
            "synthetic ingest names required",
        )
        require(
            bool(re.fullmatch(r"[a-z][a-z0-9_-]*", sample["environment"]))
            and sample["omics_layer"] == "dna"
            and type(sample["sample_no"]) is int
            and sample["sample_no"] >= 1,
            "invalid ingest template",
        )
        require(sample.get("files") == INGEST_FILES, "fixed synthetic ingest file required")


def envelope(body: object) -> dict:
    """Reject application errors even when transported with HTTP 200.

    Args:
        body: Decoded response JSON.

    Returns:
        Valid object without an error indicator.

    Raises:
        LoadError: Payload is not an object or declares failure.
    """
    require(isinstance(body, dict), "invalid JSON envelope")
    require(
        not body.get("error") and not body.get("errors") and body.get("success") is not False,
        "application failure",
    )
    status = body.get("status")
    require(not (type(status) is int and status >= 400), "application failure")
    require(
        not (
            isinstance(status, str)
            and (
                status.lower() in {"error", "failed", "failure", "denied", "invalid"}
                or status.isdigit()
                and int(status) >= 400
            )
        ),
        "application failure",
    )
    if isinstance(body.get("detail"), dict):
        envelope(body["detail"])
    return body


def check_about(body: dict, cfg: dict) -> None:
    """Match public deployment metadata against pins before authentication.

    Args:
        body: Public about response object.
        cfg: Validated configuration.

    Raises:
        LoadError: Environment, mount prefix, or any pinned database differs.
    """
    require(
        body["application"].get("environment") == cfg["environment"]
        and body["application"].get("environment") in NONPRODUCTION,
        "preflight environment mismatch",
    )
    script_name = body["application"].get("script_name")
    require(script_name is None or isinstance(script_name, str), "preflight SCRIPT_NAME mismatch")
    require((script_name or "").rstrip("/") == cfg["script_name"], "preflight SCRIPT_NAME mismatch")
    require(
        all(body["databases"].get(k) == v for k, v in cfg["databases"].items()),
        "preflight database mismatch",
    )


class WorkflowRunner:
    """Execute fixed requests using a Locust-compatible client or a test double."""

    def __init__(self, client, cfg: dict, account: dict, emit, sleep=time.sleep):
        """Bind one cookie session and its persona.

        Args:
            client: HTTP client exposing request context managers.
            cfg: Validated suite configuration.
            account: One selected private credential record.
            emit: Callback for sanitized end-to-end request events.
            sleep: Cooperative delay function, injectable in tests.
        """
        self.client, self.cfg, self.account = client, cfg, account
        self.emit, self.sleep = emit, sleep
        self.csrf = None
        self.logged_in = False

    def request(
        self, route: str, *, ids=None, payload=None, params=None, check=None, timeout=None
    ) -> dict:
        """Send one named request with redirects forbidden and bounded verified TLS.

        Args:
            route: Key in the fixed route catalog.
            ids: Explicit path substitutions, never URLs.
            payload: Optional JSON request body.
            params: Optional query values selected by the workflow.
            check: Additional response invariant callback.
            timeout: Optional remaining poll budget in seconds.

        Returns:
            Validated JSON response object.

        Raises:
            LoadError: Transport, HTTP, JSON, or workflow response validation failed.
        """
        method, template, expected, fields = ROUTES[route]
        path = template.format(**{k: segment(v) for k, v in (ids or {}).items()})
        headers = {"X-CSRF-Token": self.csrf} if self.csrf else {}
        with self.client.request(
            method,
            self.cfg["target_url"] + path,
            name=template,
            catch_response=True,
            allow_redirects=False,
            verify=self.cfg["verify"],
            timeout=timeout or self.cfg["request_timeout_seconds"],
            headers=headers,
            json=payload,
            params=params,
        ) as response:
            # Locust emits this metadata on context exit; do not expose request bodies or URLs.
            if isinstance(getattr(response, "request_meta", None), dict):
                response.request_meta.update(response=None, url=template, context={})
            try:
                status = response.status_code if type(response.status_code) is int else 0
                require(status == expected, f"unexpected HTTP status {status}")
                try:
                    body = envelope(response.json())
                except (ValueError, TypeError):
                    raise LoadError("invalid JSON envelope") from None
                require(
                    all(type(body.get(k)) is t for k, t in fields.items()),
                    "invalid response contract",
                )
                if route == "login":
                    require(bool(body["csrf_token"]), "missing CSRF token")
                if route == "rule_testing":
                    require(body["persisted"] is False, "preview persisted unexpectedly")
                if route == "report_preview":
                    require(
                        isinstance(body["report"].get("html"), str)
                        and bool(body["report"]["html"].strip()),
                        "empty report preview",
                    )
                if route == "ingest":
                    require(body["status"] == "accepted", "submission not accepted")
                    require(
                        bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", body["task_id"])),
                        "invalid task identifier",
                    )
                if check:
                    check(body)
            except LoadError as exc:
                response.failure(str(exc))
                raise
            response.success()
            return body

    def start(self) -> None:
        """Preflight unauthenticated, then authenticate exactly once.

        Raises:
            LoadError: Deployment pins or authentication fail.
        """
        self.request("about", check=lambda body: check_about(body, self.cfg))
        body = self.request(
            "login", payload={k: self.account[k] for k in ("username", "password", "provider")}
        )
        self.csrf = body["csrf_token"]
        self.logged_in = True

    def stop(self) -> None:
        """Log out an established session once, including its CSRF header."""
        if self.logged_in:
            self.logged_in = False
            try:
                self.request("logout")
            finally:
                self.csrf = None

    def run(self, workflow: str) -> None:
        """Execute a complete explicitly configured workflow without resource discovery.

        Args:
            workflow: Persona workflow name.

        Raises:
            LoadError: Any request or terminal ingest result fails validation.
        """
        require(workflow in self.account["workflows"], "workflow not assigned")
        fixture = self.cfg["fixtures"]
        ids = {}
        if workflow in {"browsing", "findings", "comments", "report_preview"}:
            sample = random.choice(fixture["samples"])
            ids["sample_id"] = sample["sample_id"]
        if workflow == "browsing":
            self.request(workflow, params={"search_str": ids["sample_id"], "per_page": 10})
        elif workflow == "findings":
            self.request(workflow, ids=ids)
            ids["finding_id"] = random.choice(sample["finding_ids"])
            self.request("finding", ids=ids)
        elif workflow == "genes":
            self.request(workflow, ids={"gene_id": random.choice(fixture["gene_symbols"])})
        elif workflow == "rule_testing":
            pair = random.choice(fixture["rule_tests"])
            ids = {"rule_id": pair["rule_version_id"], "sample_id": pair["sample_id"]}
            self.request(workflow, ids=ids)
        elif workflow == "report_preview":
            ids["report_type"] = sample["report_type"]
            self.request(workflow, ids=ids, params={"save": "false", "include_snapshot": "false"})
        elif workflow == "comments":
            require(self.cfg["allow_writes"], "writes disabled")
            self.request(
                workflow,
                ids=ids,
                payload={"form_data": {"sample_comment": "Synthetic load-test comment"}},
            )
        elif workflow == "ingest":
            require(self.cfg["allow_writes"], "writes disabled")
            self.ingest()
        else:
            self.request(workflow)

    def ingest(self) -> None:
        """Measure submission and bounded terminal completion as separate metrics.

        Raises:
            LoadError: Submission fails, polling expires, or the job fails.

        Notes:
            No request is retried. Created samples persist for operator cleanup.
        """
        start = time.monotonic()
        error = None
        try:
            sample = copy.deepcopy(self.cfg["fixtures"]["ingest_sample_template"])
            unique = uuid.uuid4().hex
            sample.update(name="load_sample_" + unique, case_id="load_case_" + unique)
            submitted = self.request(
                "ingest", payload={"sample": sample, "update_existing": False, "increment": False}
            )
            deadline = start + self.cfg["poll_timeout_seconds"]
            task_id = submitted["task_id"]
            for _ in range(self.cfg["max_poll_attempts"]):
                remaining = deadline - time.monotonic()
                require(remaining > 0, "ingest polling timeout")
                result = self.request(
                    "poll",
                    ids={"task_id": task_id},
                    timeout=min(remaining, self.cfg["request_timeout_seconds"]),
                    check=lambda body: check_task(body, task_id),
                )
                if result["ready"]:
                    require(time.monotonic() <= deadline, "ingest polling timeout")
                    return
                self.sleep(
                    min(self.cfg["poll_interval_seconds"], max(0, deadline - time.monotonic()))
                )
            raise LoadError("ingest polling budget exhausted")
        except LoadError as exc:
            error = LoadError(str(exc))
            raise
        finally:
            self.emit(
                request_type="WORKFLOW",
                name="ingest/terminal",
                response_time=(time.monotonic() - start) * 1000,
                response_length=0,
                exception=error,
            )


def check_task(body: dict, task_id: str) -> None:
    """Validate correlated task state and domain success, not just Celery success.

    Args:
        body: Task status envelope.
        task_id: Previously validated submitted identifier.

    Raises:
        LoadError: Correlation, state, terminal success, or result status is invalid.
    """
    require(body["task_id"] == task_id, "task correlation mismatch")
    require(body["status"] == "ok", "invalid task status")
    require(
        body["state"]
        in {"PENDING", "RECEIVED", "STARTED", "RETRY", "SUCCESS", "FAILURE", "REVOKED"},
        "invalid task state",
    )
    if body["ready"]:
        require(
            body["state"] == "SUCCESS" and body.get("successful") is True, "ingest terminal failure"
        )
        result = envelope(body.get("result"))
        require(
            result.get("status") == "ok" and bool(result.get("sample_id")), "ingest result failure"
        )
    else:
        require(body["state"] not in {"SUCCESS", "FAILURE", "REVOKED"}, "invalid task state")
