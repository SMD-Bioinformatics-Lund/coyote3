# Coyote3 Troubleshooting Manual

## 1. Purpose and Scope
This document provides actionable troubleshooting procedures for common Coyote3 failures observed in development, staging, and production-like environments. It is intended for backend engineers, DevOps engineers, support engineers, and senior analysts who need structured incident triage steps.

Coyote3 is a clinical genomics platform with a split architecture (Flask UI + FastAPI backend + MongoDB). Failures often appear at one layer while originating in another. This guide is organized by issue class and includes practical diagnostics, likely root causes, and remediation actions.

Use this document as a triage runbook. When incidents occur, begin with the section matching observed symptoms, follow the steps in order, and record outcomes. For severe incidents, preserve evidence before applying broad recovery actions.

---

## 2. General Triage Workflow (Use Before Deep Debugging)
Before diving into issue-specific sections, execute this baseline triage sequence:

1. Confirm environment (dev/stage/prod) and release version.
2. Capture timestamp and failing endpoint/page path.
3. Confirm whether issue is isolated or widespread.
4. Check service health endpoints.
5. Review recent deploy/config changes.
6. Identify whether error is auth/policy, data, or infrastructure related.

Baseline checks:

```bash
# API health
curl -sS http://<api-host>:8001/api/v1/health

# container status
docker compose ps

# recent logs (example)
docker compose logs --tail=200 api
```

If baseline checks show broad service outage, prioritize recovery and rollback workflow. If baseline checks are healthy, continue with targeted issue sections below.

---

## 3. MongoDB 3.4 Compatibility Issues
MongoDB 3.4 compatibility is an active constraint in Coyote3. Some failures occur when code or scripts assume newer Mongo features.

### 3.1 Typical symptoms
- query fails only in production-like environment
- migration scripts fail with unsupported operator errors
- inconsistent behavior between local and deployment environments

### 3.2 Common root causes
- unsupported query operators introduced
- transaction assumptions in multi-step writes
- migration scripts tested only on newer local Mongo versions

### 3.3 Actionable debugging steps
1. Confirm Mongo version on target environment.

```bash
mongo --eval 'db.version()'
```

2. Capture failing query/operator from logs.
3. Compare failing query with Mongo 3.4 supported feature set.
4. Review corresponding handler method in `api/db/*` for operator usage.
5. If migration script is failing, run in read-only dry-run mode first.

### 3.4 Remediation actions
- Replace unsupported operators with compatible equivalents.
- Refactor transactional assumptions into ordered write orchestration.
- Add regression tests for compatibility-sensitive query path.
- Document compatibility impact in release notes.

### 3.5 Prevention
- maintain compatibility checks in code review for DB-touching changes
- run migration scripts against 3.4-compatible test environment before release

---

## 4. SSH Tunnel Issues
SSH tunnels are commonly used in restricted environments for DB/API diagnostics.

### 4.1 Typical symptoms
- connection refused through expected local tunnel port
- intermittent timeout when using tunneled services
- successful SSH login but service port unreachable

### 4.2 Common root causes
- tunnel bound to wrong local/remote host/port
- tunnel process exited silently
- target service not listening on expected interface
- firewall or security group blocks remote service port

### 4.3 Actionable debugging steps
1. Verify tunnel process exists.

```bash
ps -ef | grep "ssh .* -L"
```

2. Verify local bind port is listening.

```bash
ss -lntp | grep :27017
```

3. Test direct TCP to local tunnel endpoint.

```bash
nc -vz 127.0.0.1 27017
```

4. Confirm remote host can reach target service port.
5. Recreate tunnel with explicit options:

```bash
ssh -N -L 27017:127.0.0.1:27017 user@bastion-host
```

### 4.4 Remediation actions
- use explicit `127.0.0.1` target binding where required
- add keepalive options for long-running sessions
- move to managed tunneling approach if repeated instability

### 4.5 Prevention
- standardize tunnel commands in team runbook
- avoid ad hoc local port reuse conflicts

---

## 5. Session Failures
Session failures affect authentication continuity and can appear as random authorization errors.

### 5.1 Typical symptoms
- users repeatedly redirected to login
- API responds `401` after successful login
- intermittent “whoami” failures

### 5.2 Common root causes
- cookie not set or not forwarded
- session secret mismatch across containers
- secure/samesite cookie settings incompatible with environment access pattern
- clock skew affecting session token validity

### 5.3 Actionable debugging steps
1. Verify login response sets cookie.
2. Verify subsequent requests include cookie header.
3. Check `SECRET_KEY` consistency across relevant services.
4. Validate session cookie policy against current protocol (http/https).
5. Call whoami endpoint after login:

```bash
curl -i -b cookie.txt -c cookie.txt http://<api-host>:8001/api/v1/auth/whoami
```

### 5.4 Remediation actions
- fix cookie forwarding in UI integration layer
- align secret configuration across services
- correct secure cookie setting for deployment protocol
- restart services after secret/config correction

### 5.5 Prevention
- include auth flow smoke checks in post-deploy validation
- avoid secret drift by centralizing secret injection

---

## 6. Permission Mismatch Debugging
Permission mismatch occurs when expected actions are denied or unexpected actions are allowed.

### 6.1 Typical symptoms
- user cannot perform expected action (`403`)
- user can perform action expected to be denied
- UI control visibility inconsistent with runtime authorization outcome

### 6.2 Common root causes
- role grants missing expected permission
- deny permission overrides grant unexpectedly
- endpoint requires permission not documented in role design
- stale session context after policy update

### 6.3 Actionable debugging steps
1. Capture failing endpoint path and status.
2. Retrieve authenticated user policy context (`whoami`).
3. Compare required endpoint permission with effective user permissions.
4. Check deny permissions for overrides.
5. Verify route dependency (`require_access`) in route module.
6. Re-login to refresh session context after policy changes.

### 6.4 Remediation actions
- update role or user permission mapping via admin governance flow
- remove incorrect deny entries
- update endpoint requirement if policy intent changed
- add/adjust permission matrix tests

### 6.5 Prevention
- test role x permission x deny matrix for policy changes
- keep policy docs and endpoint checks synchronized

---

## 7. Audit Not Logging
Audit gaps are high-severity in regulated workflows.

### 7.1 Typical symptoms
- expected privileged action has no audit entry
- only partial event fields captured
- audit rate drops unexpectedly after deploy

### 7.2 Common root causes
- service path mutation missing audit emission call
- audit sink misconfiguration
- exception path bypasses audit emission
- logging pipeline retention/rotation issue

### 7.3 Actionable debugging steps
1. Identify exact action and expected event type.
2. Reproduce action in controlled test case.
3. Inspect service method for audit emission point.
4. Check whether errors short-circuit event path.
5. Validate audit storage/sink availability.
6. Verify log folder or collection location.

### 7.4 Remediation actions
- add audit emission at service authority point
- ensure both success/failure paths are handled per policy
- repair audit sink routing configuration
- backfill incident report documenting missing event window

### 7.5 Prevention
- enforce audit tests for privileged mutation endpoints
- include audit continuity checks in post-release validation

---

## 8. Version Rewind Inconsistencies
Rewind inconsistencies affect governance confidence and policy traceability.

### 8.1 Typical symptoms
- rewind appears successful but effective document state is unexpected
- changelog entries missing or non-sequential
- dependent workflow still reflects newer values after rewind

### 8.2 Common root causes
- rewind applies stale revision payload format
- related caches/config reload not triggered
- changelog metadata incomplete
- partial write sequencing in rewind path

### 8.3 Actionable debugging steps
1. Retrieve current document and full changelog.
2. Verify target revision payload and metadata.
3. Confirm rewind created new revision entry (not destructive overwrite).
4. Verify dependent services re-read updated state.
5. Execute endpoint-level verification for affected workflow.

### 8.4 Remediation actions
- fix rewind service to apply validated revision snapshot
- enforce mandatory changelog metadata
- clear or refresh caches where applicable
- add regression tests for rewind path

### 8.5 Prevention
- require rewind tests for every versioned entity family
- prohibit manual DB rewrites for governed entities

---

## 9. Missing Schema Rendering
Schema rendering failures appear as missing fields or broken admin/edit pages.

### 9.1 Typical symptoms
- form loads without expected fields
- schema-driven page fails with `400` or `500`
- newly added schema type does not appear in UI context

### 9.2 Common root causes
- schema document missing required keys (`schema_type`, `version`, `fields`)
- schema not active or not mapped in route/service context
- profile-specific nested config missing expected branch
- frontend template assumes field exists without fallback

### 9.3 Actionable debugging steps
1. Fetch schema document by id from admin context endpoint.
2. Validate required schema keys and field structure.
3. Confirm schema `is_active` and category mapping.
4. Verify route/service selects correct schema id.
5. Inspect UI rendering path for missing-field assumptions.

### 9.4 Remediation actions
- fix schema document structure and version metadata
- update schema selection logic in service layer
- add template fallbacks where appropriate
- add schema validation tests

### 9.5 Prevention
- enforce schema validator before persistence
- include schema-driven page tests for new schema types

---

## 10. Docker Build Failures
Build failures delay release and often indicate dependency or context misconfiguration.

### 10.1 Typical symptoms
- image build fails on dependency install
- build context missing required files
- runtime image starts but fails import at startup

### 10.2 Common root causes
- inconsistent requirements lock state
- Dockerfile path/copy mismatch
- dependency requiring unavailable system toolchain
- stale build cache masking prior errors

### 10.3 Actionable debugging steps
1. run clean build with no cache.

```bash
docker compose build --no-cache api web
```

2. inspect first failing layer output.
3. verify `requirements.txt` and `pyproject.toml` consistency.
4. verify Dockerfile `COPY` paths match repository layout.
5. run import checks inside built container.

```bash
docker run --rm coyote3-api:<tag> python -m compileall -q api
```

### 10.4 Remediation actions
- fix dependency pin conflicts
- correct Dockerfile copy/build stages
- add missing OS-level dependencies explicitly
- pin reproducible build tools versions

### 10.5 Prevention
- build in CI on every PR
- keep dependency updates isolated and tested

---

## 11. Log Location Reference
Use this section as quick reference during incident triage.

### 11.1 Recommended log folders
```text
/var/log/coyote3/
  web/
    app.log
    error.log
  api/
    app.log
    error.log
  access/
    web_access.log
    api_access.log
  audit/
    audit_events.log
```

### 11.2 Container log access commands
```bash
docker compose logs --tail=300 web
docker compose logs --tail=300 api
docker compose logs --tail=300 mongo
```

### 11.3 What to look for
- repeated auth failures (`401`)
- forbidden spikes (`403`)
- report save conflicts (`409`)
- exception traces for same route family
- missing audit event patterns

---

## 12. Performance Bottleneck Identification
Performance issues can originate from DB queries, route orchestration, or environment resource contention.

### 12.1 Typical symptoms
- slow sample/variant pages
- delayed report preview/save
- increased API latency under moderate load

### 12.2 Common root causes
- missing or inefficient indexes
- unbounded payload endpoints
- N+1 query patterns
- container CPU/memory throttling
- high I/O latency on storage volumes

### 12.3 Actionable debugging steps
1. identify slow endpoint and p95/p99 latency.
2. map endpoint to route/service/handler path.
3. inspect query patterns and index coverage.
4. check container resource usage.

```bash
docker stats
```

5. test endpoint with controlled parameters (pagination/filter).
6. compare latency with and without optional payload expansions.

### 12.4 Remediation actions
- add/adjust indexes based on observed query path
- enforce pagination limits
- refactor N+1 handler calls to batch queries
- tune container resource allocations
- optimize projections to reduce payload size

### 12.5 Prevention
- include performance checks on high-volume routes in release validation
- monitor route-family latency trends continuously

---

## 13. Additional Common Issue: Configuration Drift
Configuration drift between services/environments is a common hidden cause.

### 13.1 Symptoms
- behavior differs between web and api despite same code release
- one service passes auth while another fails policy checks

### 13.2 Debugging steps
1. diff effective environment variables for web and api containers.
2. verify secrets and tokens loaded from correct source.
3. confirm report path and DB URI alignment.

### 13.3 Remediation
- standardize env templates
- enforce startup validation for required variables
- add config diff checks to release process

---

## 14. Incident Escalation Guidance
Escalate immediately when:
- clinical report save/export is broadly failing
- unauthorized access is suspected
- audit event pipeline is disrupted
- data consistency issues cannot be bounded quickly

Provide in escalation package:
- timestamp window
- affected endpoints/pages
- sample/report identifiers (where relevant)
- error snippets and log references
- recent deployment/config change context

---

## 15. Post-Fix Validation Checklist
After applying a fix, verify:
- [ ] health endpoint green
- [ ] auth workflow functional
- [ ] affected route family functional
- [ ] permission behavior validated
- [ ] audit continuity confirmed (if applicable)
- [ ] no new critical alerts

For production incidents, add a postmortem and regression tests before closure.

---

## 16. Preventive Controls Summary
To reduce recurrence:
- maintain route-family regression tests
- enforce permission matrix tests for policy changes
- validate schema documents on write
- run restore drills for backup confidence
- keep docs and runbooks updated with incident learnings

---

## 17. Assumptions
ASSUMPTION:
- Coyote3 deployment uses Docker-based topology in at least development and controlled environments.
- Logs are available through container runtime and/or host log folders.
- MongoDB compatibility target remains 3.4.

---

## 18. Future Evolution Considerations
1. add automated troubleshooting diagnostics script for common checks
2. add route-family synthetic probes for early failure detection
3. add policy drift detector for role/permission changes
4. add incident templates with prefilled evidence fields
5. integrate performance regression checks into CI for high-risk endpoints
