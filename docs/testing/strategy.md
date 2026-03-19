# Coyote3 Testing Strategy and Quality Assurance Policy

## 1. Purpose and Policy Scope
This document defines the mandatory testing strategy for Coyote3. It is written as an internal quality assurance policy for engineering, QA, DevOps, and release governance stakeholders. The policy applies to all code paths that influence user workflows, authorization behavior, report lifecycle, schema-driven configuration, and audit traceability.

Coyote3 supports clinical genomics workflows where correctness and reproducibility are required outcomes, not optional quality goals. Therefore testing is treated as a control framework, not only a developer convenience. The policy requires layered testing, deterministic test data, explicit access-control verification, and release gates that prevent unsafe changes from reaching production environments.

This strategy emphasizes practical implementation details while maintaining governance rigor. Teams should use it both as day-to-day engineering guidance and as release-time compliance evidence reference.

---

## 2. Testing Objectives
Testing in Coyote3 must continuously validate the following objectives:

1. **Functional correctness**: domain workflows return expected behavior across nominal and error paths.
2. **Contract stability**: API request/response patterns remain consistent and backward-safe.
3. **Authorization correctness**: protected operations fail closed for unauthorized contexts.
4. **Audit traceability**: privileged and clinically relevant actions emit expected audit events.
5. **Architecture integrity**: UI/API boundaries and route organization conventions remain enforced.
6. **Operational confidence**: release candidates are validated by test and coverage evidence.

If a change cannot be verified against these objectives, it is considered incomplete.

---

## 3. Test Layer Model
Coyote3 uses a layered testing model to align risk with verification depth.

### 3.0 Current enforced suite structure
The repository now enforces four primary suites as first-class quality gates:

- `tests/unit/`: core/security/infra-focused logic tests with high isolation.
- `tests/api/`: FastAPI route and policy behavior tests.
- `tests/ui/`: Flask presentation and UI->API boundary tests.
- `tests/integration/`: architectural guardrails and cross-layer contract tests.

These suites are not only organizational; they are wired into both CI and local pre-commit hooks. The reason is to make boundary regressions fail fast before merge. Historically, architecture regressions were often detected late when broad route tests passed but boundary rules were silently violated. Marker-based suites with explicit scope reduce that risk.

## 3.1 Unit tests
Unit tests validate isolated functions or small service methods using controlled stubs/mocks.

### What unit tests should verify
- normalization logic
- value coercion
- deterministic helper behavior
- error branch behavior in service methods

### Why unit tests matter
Unit tests provide fast feedback on pure logic regressions and reduce debugging cost before broader integration runs.

### Common mistakes
- over-mocking to the point where behavior under test is no longer realistic
- relying on external mutable state in unit tests

## 3.2 Integration tests
Integration tests validate route-family behavior and service orchestration against fixture-backed fake stores or test adapters.

### What integration tests should verify
- request validation
- policy gating
- service orchestration path
- expected response structure

### Why integration tests matter
Most production regressions occur at component boundaries, not in isolated helper functions. Integration tests target these boundaries.

## 3.3 Architecture guardrail tests
Architecture tests enforce non-functional invariants such as import boundaries and route security conventions.

### Examples
- UI must not import backend business modules directly
- protected routes must be guarded by auth/permission checks
- route module organization standards remain consistent
- UI must not import Mongo/BSON driver modules (`pymongo`, `flask_pymongo`, `motor`, `bson`)

---

## 4. Unit Testing Patterns
## 4.1 Pattern: pure function validation
Use direct inputs and deterministic assertions for transformation helpers.

```python
def test_coerce_nonnegative_int_handles_invalid_values():
    assert coerce_nonnegative_int('5') == 5
    assert coerce_nonnegative_int('-1', default=7) == 7
    assert coerce_nonnegative_int(None, default=9) == 9
```

### Why this pattern
Fast and precise tests catch regressions in logic-heavy utility paths.

## 4.2 Pattern: service branch validation
Service tests should validate both success and failure branches with mocked dependencies.

```python
def test_prepare_report_output_conflict(monkeypatch):
    monkeypatch.setattr(os.path, 'exists', lambda _: True)
    with pytest.raises(AppError) as exc:
        prepare_report_output('/reports', '/reports/r1.html')
    assert exc.value.status_code == 409
```

### Why this pattern
Service branches include critical domain guarantees such as conflict handling and write failure behavior.

## 4.3 Unit test quality standards
- no external network calls
- deterministic assertions
- no hidden dependency on test execution order
- explicit fixture/setup usage

---

## 5. Integration Testing Strategy
Integration testing in Coyote3 is route-family oriented and fixture-backed.

## 5.1 Route-family grouping
Route tests are grouped by module families:
- admin
- dna
- rna
- reports
- home
- common
- public
- system/internal

Grouping tests this way aligns with ownership boundaries and allows targeted regression execution.

## 5.2 Fake-store harness
A shared fake-store harness should mimic handler behavior to test service/route orchestration without requiring live database dependencies.

### Why harness approach
- deterministic behavior
- high speed
- no environment fragility
- easier scenario control

## 5.3 Integration scenario coverage minimum
Every new route should include tests for:
- success path
- validation failure
- unauthorized/forbidden path
- not-found/conflict path where applicable

### Example integration test

```python
def test_internal_roles_levels_returns_map(monkeypatch):
    monkeypatch.setattr(internal, '_require_internal_token', lambda _req: None)
    monkeypatch.setattr(internal.store.roles_handler, 'get_all_roles', lambda: [{'_id': 'admin', 'level': 99}])
    payload = internal.get_role_levels_internal(request=object())
    assert payload['role_levels'] == {'admin': 99}
```

---

## 6. API Testing Policy
API tests validate contract behavior at endpoint boundaries.

## 6.1 API contract expectations
- deterministic status code behavior
- predictable envelope structure
- stable error payload keys

## 6.2 API test domains
- auth endpoints
- route-family endpoints
- pagination/filter parameter behavior
- error handling behavior

## 6.3 Example API-style behavior test

```python
def test_auth_login_invalid_credentials(monkeypatch):
    monkeypatch.setattr(system, 'authenticate_credentials', lambda *_: None)
    with pytest.raises(HTTPException) as exc:
        system.auth_login(system.ApiAuthLoginRequest(username='u', password='bad'))
    assert exc.value.status_code == 401
```

## 6.4 API contract drift prevention
When route contracts change, tests and API docs must be updated in same change set.

---

## 7. Permission Testing Policy
Permission tests are mandatory for all protected route families.

## 7.1 Required permission test categories
1. authenticated + authorized
2. authenticated + missing permission
3. authenticated + denied permission override
4. unauthenticated access

## 7.2 Example permission test

```python
def test_permission_denied_overrides_role_grant():
    user = ApiUser(
        id='u1',
        email='x@y.z',
        fullname='User',
        username='user',
        role='analyst',
        access_level=100,
        permissions=['view_sample'],
        denied_permissions=['view_sample'],
        assays=[],
        assay_groups=[],
        envs=[],
        asp_map={},
    )

    checker = require_access(min_level=1, permissions=['view_sample'])
    with pytest.raises(HTTPException) as exc:
        checker(user)
    assert exc.value.status_code == 403
```

## 7.3 Why permission tests are critical
Authorization regressions can expose clinical data or permit unauthorized mutation actions. These defects are high severity and must be blocked pre-merge.

---

## 8. Audit Testing Policy
Audit testing validates that privileged and clinically significant operations produce expected audit events.

## 8.1 Required audit test conditions
- event emitted on successful mutation
- event emitted or failure path recorded where policy requires on mutation failure
- event envelope fields include actor, entity, result, timestamp

## 8.2 Example audit event test sketch

```python
def test_report_save_emits_audit_event(monkeypatch):
    captured = {}

    monkeypatch.setattr(report_service, 'emit_audit_event', lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(report_service, 'persist_report_and_snapshot', lambda **_: 'r1')

    report_service.save_report(sample_id='s1', payload={}, user=fake_user())

    assert captured['event_type'] == 'report.save'
    assert captured['result'] == 'success'
```

## 8.3 Why audit tests matter
Audit coverage ensures traceability is preserved as service logic evolves.

---

## 9. Coverage Expectations
Coverage is required as a quality signal and prioritization tool.

## 9.1 Required coverage commands

```bash
PYTHONPATH=. .venv/bin/pytest -q tests
./scripts/run_tests_with_coverage.sh
```

Coverage execution is standardized through `.coveragerc` and the project script.
This command is the release gate for coverage evidence and produces:
- terminal missing-lines coverage output
- HTML report at `.coverage_html/index.html`

## 9.2 Coverage policy guidance
- use coverage to prioritize high-risk untested code
- do not treat line coverage alone as proof of quality
- ensure security-sensitive routes and services have strong branch/path coverage

## 9.3 Minimum practical expectations
- all new or modified routes must have behavior tests
- high-risk modules (auth, policy, reporting, schema validation) should not be merged with weak coverage deltas

---

## 10. Mutation Testing Recommendations
Mutation testing helps detect weak assertions that survive logical modifications.

## 10.1 Operational recommendation
Run mutation testing in isolated environment to prevent dependency conflicts with main test stack.

```bash
python3 -m venv .venv-mutation
.venv-mutation/bin/pip install -U pip wheel setuptools
.venv-mutation/bin/pip install -r requirements.txt
```

## 10.2 Suggested mutation scope
Start with critical modules:
- workflow filter normalization
- reporting pipeline
- route-level auth/security helpers

## 10.3 Mutation policy
- mutation testing is advisory or scheduled gate unless organization defines blocking thresholds
- survivors should generate test hardening tasks

## 10.4 Why mutation testing is useful
It identifies tests that execute code but fail to assert meaningful behavior.

---

## 11. Mocking MongoDB and Data Access
Mongo behavior should be simulated through handler-level abstractions, not ad hoc global patching.

## 11.1 Mocking policy
- use fake-store harness for integration tests
- mock handler methods in service tests
- avoid live database dependence in default test pipeline

## 11.2 Why handler-level mocking
It preserves contract realism while keeping tests deterministic and fast.

## 11.3 Common mistakes
- mocking deep internals rather than handler interfaces
- using production snapshots with sensitive data
- shared mutable fake stores across tests

---

## 12. Test Data Isolation
Test data should be deterministic, minimal, and isolated.

## 12.1 Isolation requirements
- no test should rely on execution order
- fixtures should not leak state across tests
- snapshots should be sanitized and local

## 12.2 Fixture design approach
- provide reusable factory-style fixtures
- include role/sample/variant defaults with override support
- maintain clear mapping to collection shapes

### Example fixture

```python
import pytest

@pytest.fixture
def sample_doc():
    return {
        '_id': 's1',
        'SAMPLE_ID': 'SAMPLE_001',
        'assay': 'WGS',
        'case_id': 'CASE001',
        'filters': {'min_depth': 100}
    }
```

## 12.3 Why isolation matters
Non-isolated tests create flaky CI behavior and reduce trust in failures.

---

## 13. Example Pytest Structure
Recommended structure:

```text
tests/
  conftest.py
  api/
    fixtures/
      fake_store.py
      mock_collections.py
    services/
      test_filter_normalization.py
      test_reporting_pipeline_and_paths.py
    routers/
      test_system_routes.py
      test_internal_routes.py
      test_dna_routes.py
      test_reports_routes.py
      ...
    test_access_control_matrix.py
    test_api_route_security.py
    test_route_module_organization.py
  web/
    test_web_api_boundary.py
    test_web_api_integration_helpers.py
```

Why this structure:
- aligns tests with architecture ownership
- supports targeted route-family regression runs
- keeps fixtures centralized and reusable

---

## 14. Example API Test (Route Behavior)

```python
def test_health_endpoint_returns_ok():
    payload = system.health()
    assert payload == {'status': 'ok'}


def test_auth_me_returns_serialized_user(monkeypatch):
    monkeypatch.setattr(system, 'serialize_api_user', lambda user: {'username': user.username})
    monkeypatch.setattr(system.util.common, 'convert_to_serializable', lambda payload: payload)

    payload = system.auth_me(user=fake_api_user())
    assert payload['status'] == 'ok'
    assert payload['user']['username'] == 'tester'
```

This pattern validates route-level contract behavior with minimal dependency complexity.

---

## 15. CI Enforcement Strategy
CI is a mandatory policy gate. A passing local run is useful but not sufficient.

## 15.1 Required CI stages
1. dependency setup
2. compile/import checks
3. test suite execution
4. coverage generation
5. architecture guardrails
6. documentation impact validation

## 15.2 Minimum quality gates
A merge should be blocked when any of the following fail:
- test suite failures
- protected route security guardrail failures
- boundary tests indicating architecture violations
- critical policy modules changed without matching tests

## 15.3 Example command sequence

```bash
PYTHONPATH=. .venv/bin/python -m compileall -q api coyote tests
PYTHONPATH=. .venv/bin/pytest -q tests
PYTHONPATH=. .venv/bin/pytest -q tests --cov=api --cov=coyote --cov-report=term-missing --cov-report=xml
```

## 15.4 Why CI gates are strict
In a clinical platform, post-merge discovery of security or workflow regressions is unacceptable when pre-merge automation could have prevented release.

---

## 16. Quality Gate Definitions (Policy)
Define explicit gate outcomes to avoid subjective release decisions.

## 16.1 Gate A: Structural integrity
- imports compile
- no syntax errors
- architecture boundary tests pass

## 16.2 Gate B: Behavioral correctness
- route-family tests pass
- service tests pass
- key workflow tests pass

## 16.3 Gate C: Security and policy integrity
- permission matrix tests pass
- route security tests pass
- internal route protection tests pass

## 16.4 Gate D: Evidence and documentation
- coverage report generated
- docs updated when contract/policy changes occur

---

## 17. Common Testing Failures and How to Correct Them
### 17.1 Flaky tests
Cause: shared mutable fixture state.
Fix: isolate fixtures, avoid global mutations.

### 17.2 False-positive authorization tests
Cause: mocked dependency bypasses `require_access` behavior.
Fix: include explicit dependency-behavior tests and negative-path checks.

### 17.3 Contract drift issues
Cause: endpoint payload changed but tests too generic.
Fix: assert payload key semantics and required fields explicitly.

### 17.4 Slow suites
Cause: unnecessary integration depth in unit tests.
Fix: enforce unit/integration boundary and targeted execution profiles.

---

## 18. Testing Change Workflow for New Features
When adding a feature:
1. define expected behavior and policy matrix
2. add unit tests for pure/service logic
3. add route integration tests for endpoint behavior
4. add permission-negative tests
5. add audit checks for privileged mutations
6. run full suite + coverage
7. update docs and endpoint catalog

This sequence reduces late-stage rework and keeps quality artifacts aligned with implementation.

---

## 19. Assumptions
ASSUMPTION:
- Pytest is the standard framework.
- Test suites are organized under `tests/api`, `tests/ui`, and `tests/integration`.
- Coyote3 policy and route guardrails are enforced by dedicated tests already present in repository.

---

## 20. Future Evolution Considerations
1. Add automated OpenAPI contract snapshot validation.
2. Introduce performance regression suite for high-volume endpoints.
3. Add scheduled mutation test runs for critical modules.
4. Build requirement-to-test traceability links in CI artifacts.
5. Add policy simulation harness for role/permission change previews.

---

## 21. QA Operating Model and Ownership
A testing strategy is only effective when ownership and execution responsibilities are explicit. In Coyote3, quality ownership is shared but role-specific. Feature engineers own primary test implementation for the code they change. Reviewers own validation of test completeness and risk alignment. QA-focused engineers own cross-cutting regression strategy and test architecture quality. DevOps engineers own pipeline reliability and artifact retention. Release managers own gate enforcement and evidence packaging.

This shared model prevents quality from becoming a late-stage handoff activity. For each merge request, the author should explicitly state which test layers were touched, which risk categories were affected, and whether policy/security behavior changed. Reviewers should challenge weak or missing negative-path tests and should verify that test assertions are meaningful rather than superficial. For example, a test that only checks status `200` without verifying key response fields is often insufficient for contract-sensitive endpoints.

A common anti-pattern in many teams is “QA will catch it later.” In Coyote3 this is unacceptable because policy and reporting regressions can propagate quickly. Test quality must be built into feature development flow. QA-led exploratory testing remains valuable, but it does not replace deterministic automated verification at route and service boundaries.

---

## 22. Release Evidence and Verification Artifacts
Testing output should be retained as release evidence, not discarded as transient console text. For regulated environments, evidence should allow a reviewer to answer: what was tested, against which revision, with what results, and what known risk remains.

## 22.1 Required release evidence artifacts
1. test execution summary
2. coverage report (`coverage.xml` and/or rendered summaries)
3. list of changed modules and corresponding tests
4. policy-impact confirmation for role/permission changes
5. report workflow validation notes when reporting paths changed

## 22.2 Why artifact retention exists
Without artifact retention, release confidence depends on human memory and ad hoc communication. That is insufficient for post-incident analysis and compliance review.

## 22.3 Evidence packaging example
```text
release-evidence/
  build-info.txt
  test-summary.txt
  coverage.xml
  security-guardrails.txt
  route-family-results.txt
  docs-impact.txt
```

## 22.4 Audit and security relevance
For security-sensitive changes, include explicit outputs from access matrix and route protection tests. For audit-sensitive changes, include proof that audit event tests passed for affected mutations.

---

## 23. Advanced Permission and Policy Test Matrix Guidance
Permission testing should include more than single happy-path role checks. Use matrices that model realistic combinations:
- role grants only
- role grants + user deny
- no grants
- elevated level but missing permission
- permission granted but endpoint-specific validation failure

A robust matrix catches subtle regressions in override logic and role evolution. Policy regressions are often introduced when new permissions are added without revisiting existing deny assumptions.

### Matrix example concept
```text
Role=analyst, Perm=view_sample, Deny=[] -> allow read endpoint
Role=analyst, Perm=view_sample, Deny=[view_sample] -> deny read endpoint
Role=admin, Level=999, Perm=[] -> deny if endpoint requires explicit permission
Role=admin, Level=999, Perm=create_role -> allow create role endpoint
```

### Practical recommendation
Automate matrix tests for high-risk families (`admin`, `reports`, policy-mutation routes) and run them on every CI merge pipeline.

---

## 24. API Regression Testing Beyond Route Functions
Direct route-function tests are fast and useful, but API quality also depends on integration semantics, including error model consistency and payload shape stability. Introduce regression tests that validate representative endpoint contracts as snapshots or explicit schema assertions.

### Suggested regression assertions
- required top-level keys exist (`status`, `data` where expected)
- error payloads include `status` and `error`
- pagination payload contains stable metadata keys
- ids remain string-typed where contract requires strings

### Why this matters
Even small refactors can accidentally rename fields or alter nesting. UI and internal consumers can break silently if regression tests are too shallow.

---

## 25. Test Environment Profiles and Isolation Boundaries
Coyote3 tests should run reliably in local and CI environments without external service dependency by default. When optional integration tests require environment services, they should be explicitly marked and separated.

## 25.1 Recommended profile split
- default profile: deterministic local/CI tests without live network dependencies
- optional profile: environment-backed integration checks
- scheduled profile: extended mutation/performance checks

## 25.2 Why profile split is useful
It preserves fast feedback loops while still enabling deeper confidence checks in controlled pipelines.

## 25.3 Isolation requirements
- no writes to production resources
- no secrets required for default test execution
- deterministic fixture setup and cleanup

---

## 26. Quality Gate Escalation and Exception Policy
There may be cases where a known test issue cannot be fixed immediately. Exception handling should be controlled and temporary.

## 26.1 Exception requirements
- explicit issue reference
- clear risk statement
- temporary duration and owner
- remediation due date

## 26.2 Non-negotiable gates
Exceptions should not bypass core security and policy gates (authentication/authorization guardrails) without formal high-level approval.

## 26.3 Why strict exception policy exists
Untracked gate bypasses accumulate invisible risk and undermine confidence in release quality controls.

---

## 27. QA Metrics and Continuous Improvement
Testing strategy should be measured and improved continuously.

Suggested metrics:
- flake rate
- average time to detect regression in CI
- high-risk module coverage trend
- permission regression incident count
- mutation survivor trend (where mutation testing is used)

Use these metrics to prioritize test debt reduction and to identify unstable parts of the system.

---

## 28. Additional Coverage Command Examples

```bash
# Route-family focused run
PYTHONPATH=. .venv/bin/pytest -q tests/api/routers/test_reports_routes.py --cov=api/routers/reports.py --cov-report=term-missing

# Service-focused run
PYTHONPATH=. .venv/bin/pytest -q tests/unit --cov=api/core --cov=api/security --cov=api/infra --cov-report=term-missing

# Web boundary focused run
PYTHONPATH=. .venv/bin/pytest -q tests/ui --cov=coyote/services/api_client --cov-report=term-missing
```

These focused commands are useful during development, but final merge validation should still include full suite coverage.

---

## 29. Future Evolution Considerations (QA)
1. Add contract-schema validation generated from OpenAPI models.
2. Add end-to-end synthetic workflow tests against isolated staging.
3. Integrate scheduled mutation testing reports into weekly quality review.
4. Introduce static checks for audit event emission on privileged service mutations.
5. Expand requirement-to-test traceability reporting as part of release evidence.
