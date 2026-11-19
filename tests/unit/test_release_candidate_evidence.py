"""Release acceptance rejects skipped tests, stale evidence and incomplete cleanup."""

import json

import pytest

from scripts.release.check_candidate import browser_result, gate, junit_result


@pytest.mark.parametrize("outcome", ["failure", "error", "skipped"])
def test_backend_cannot_pass_with_an_unexecuted_or_unsuccessful_case(tmp_path, outcome):
    report = tmp_path / "tests.xml"
    report.write_text(
        f'<testsuites><testsuite tests="1"><testcase name="regression"><{outcome}/></testcase></testsuite></testsuites>'
    )
    with pytest.raises(ValueError, match="all execute and pass"):
        junit_result(report)


def test_backend_report_requires_cases_and_complete_counts(tmp_path):
    report = tmp_path / "tests.xml"
    for content in ["<testsuites/>", '<testsuite tests="2"><testcase/></testsuite>']:
        report.write_text(content)
        with pytest.raises(ValueError):
            junit_result(report)
    report.write_text('<testsuite tests="1"><testcase name="regression"/></testsuite>')
    assert junit_result(report)["passed"] == 1


def browser_files(directory):
    run = {
        "source_commit": "a" * 40,
        "source_dirty": False,
        "synthetic_only": True,
        "browser_exit_code": 0,
        "remaining_resources": {"container": [], "network": [], "volume": []},
        "images": {"worker": "sha256:synthetic"},
    }
    results = {"stats": {"expected": 3, "unexpected": 0, "flaky": 0, "skipped": 0}}
    (directory / "run.json").write_text(json.dumps(run))
    (directory / "browser-results.json").write_text(json.dumps(results))
    return run, results


@pytest.mark.parametrize(
    "fault", ["commit", "dirty", "cleanup", "skip", "flaky", "failure", "empty"]
)
def test_browser_rejects_missing_acceptance_or_wrong_source(tmp_path, fault):
    run, results = browser_files(tmp_path)
    if fault == "commit":
        run["source_commit"] = "b" * 40
    elif fault == "dirty":
        run["source_dirty"] = True
    elif fault == "cleanup":
        run["remaining_resources"]["volume"] = ["leftover"]
    elif fault == "skip":
        results["stats"]["skipped"] = 1
    elif fault == "flaky":
        results["stats"]["flaky"] = 1
    elif fault == "failure":
        run["browser_exit_code"] = 1
    else:
        results["stats"]["expected"] = 0
    (tmp_path / "run.json").write_text(json.dumps(run))
    (tmp_path / "browser-results.json").write_text(json.dumps(results))
    with pytest.raises(ValueError, match="incomplete, failed"):
        browser_result(tmp_path, "a" * 40)


def test_gate_requires_both_jobs_on_the_same_commit(tmp_path):
    backend, browser = tmp_path / "backend.json", tmp_path / "browser.json"
    for kind, path in [("backend", backend), ("browser", browser)]:
        path.write_text(
            json.dumps(
                {
                    "kind": kind,
                    "status": "passed",
                    "source_commit": "a" * 40,
                    "result": {"passed": 2},
                }
            )
        )
    assert set(gate([backend, browser], "a" * 40)) == {"backend", "browser"}
    for records, commit in [
        ([backend], "a" * 40),
        ([backend, backend], "a" * 40),
        ([backend, browser], "b" * 40),
    ]:
        with pytest.raises(ValueError, match="requires successful backend and browser"):
            gate(records, commit)
