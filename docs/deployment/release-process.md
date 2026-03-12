# Coyote3 Release Process

## 1. Purpose
This document defines the internal release governance process for Coyote3. It establishes required controls for branch management, versioning, tagging, changelog quality, QA validation, database compatibility checks, deployment approvals, and rollback readiness.

Coyote3 is a clinical genomics platform with regulated workflow implications. Therefore release activities must be repeatable, auditable, and policy-driven. Informal release behavior is not acceptable.

---

## 2. Scope
This policy applies to:
- application code releases (API + web)
- configuration releases affecting runtime behavior
- schema/data-model compatible releases
- security and policy-impacting releases

It covers development through production release closure.

---

## 3. Branching Model

## 3.1 Branch roles
- `main`: production-ready history; protected branch.
- `develop` (optional by team policy): integration branch for upcoming release train.
- `feature/<scope>-<short-name>`: feature development branches.
- `hotfix/<scope>-<short-name>`: urgent production fixes.
- `release/<version>`: stabilization branch for a target release.

## 3.2 Branch rules
- direct pushes to `main` are prohibited.
- all merges require pull request review and CI pass.
- feature branches must be rebased or merged cleanly with target branch before release cut.
- hotfix branches must include regression tests and post-merge backport to active integration branch.

## 3.3 Why this model exists
It separates feature velocity from release stabilization and reduces risk of uncontrolled production changes.

---

## 4. Semantic Versioning Strategy
Coyote3 uses semantic versioning for release communication and artifact governance.

Format:

```text
MAJOR.MINOR.PATCH
```

## 4.1 MAJOR
Increment MAJOR when introducing breaking API/behavior changes requiring explicit client migration.

## 4.2 MINOR
Increment MINOR for backward-compatible feature additions and significant non-breaking enhancements.

## 4.3 PATCH
Increment PATCH for backward-compatible bug fixes, security fixes, and behavior corrections that do not alter public contracts.

## 4.4 Pre-release identifiers
For staged validation:
- `1.7.0-rc.1`
- `1.7.0-rc.2`

Pre-release identifiers must not be used as final production version tags.

## 4.5 Version decision rules
- If endpoint behavior breaks consumers, MAJOR is required.
- If endpoint adds optional fields and remains compatible, MINOR.
- If fix does not alter expected contract shape, PATCH.

---

## 5. Tagging Conventions

## 5.1 Tag format
Release tags must be immutable and follow:

```text
v<MAJOR>.<MINOR>.<PATCH>
```

Examples:
- `v1.4.2`
- `v2.0.0`

## 5.2 Release candidate tags
Optional staging tags:
- `v1.5.0-rc.1`

## 5.3 Tagging rules
- tags are created only after release gates pass.
- tags must point to the exact commit deployed.
- retagging is prohibited; new corrective tag required if release changes.

## 5.4 Why strict tagging exists
Immutable tags provide traceable mapping between source, artifacts, and deployment events.

---

## 6. Changelog Writing Rules
Changelog is a governance artifact, not a marketing summary.

## 6.1 Required release changelog sections
1. Version and release date
2. Scope summary
3. Added/changed/fixed items
4. Security or policy-impacting changes
5. Migration notes
6. Deprecations
7. Rollback considerations

## 6.2 Writing standards
- use precise engineering language
- include impacted modules or route families
- include explicit notes for authorization, schema, and reporting behavior changes
- include issue/PR references where available

## 6.3 Prohibited changelog patterns
- vague statements such as “misc updates”
- missing migration notes for contract-impacting changes
- combining unrelated major changes into one ambiguous line

## 6.4 Example changelog entry
```markdown
## v1.8.0 - 2026-03-03
### Changed
- API: Added strict report save conflict handling for DNA/RNA save endpoints (`/api/v1/*/report/save`), returning `409` on filename collision.
### Fixed
- UI: Normalized API integration header forwarding for session consistency.
### Security
- Enforced deny-override checks in access matrix edge cases.
### Migration Notes
- No data migration required.
### Rollback Notes
- Safe rollback to v1.7.3; no schema changes.
```

---

## 7. QA Checklist Before Release
This checklist is mandatory for production release candidates.

## 7.1 Test and quality gates
- [ ] compile/import validation passed
- [ ] full test suite passed
- [ ] security/guardrail tests passed
- [ ] coverage report generated and reviewed
- [ ] route-family tests for changed modules passed

## 7.2 Functional verification gates
- [ ] auth login/logout/whoami verified
- [ ] sample view workflows verified
- [ ] DNA/RNA critical workflows verified
- [ ] report preview/save/history verified
- [ ] admin policy workflows verified if impacted

## 7.3 Documentation gates
- [ ] changelog updated
- [ ] impacted docs updated (API/security/data/developer/user as needed)
- [ ] release notes reviewed by technical owner

## 7.4 Artifact gates
- [ ] image tags and digests recorded
- [ ] configuration diff reviewed
- [ ] rollback artifacts prepared

---

## 8. Database Compatibility Checklist
Given MongoDB 3.4 compatibility constraints, every release must verify DB compatibility.

## 8.1 Query/operator compatibility
- [ ] no unsupported MongoDB operators introduced
- [ ] no transaction assumptions introduced
- [ ] handler queries reviewed for 3.4 compatibility

## 8.2 Schema/data evolution checks
- [ ] additive schema changes documented
- [ ] migration scripts include dry-run mode
- [ ] dual-shape read support present where required
- [ ] legacy path removal not performed before validation window

## 8.3 Index impact checks
- [ ] new indexes justified by query use
- [ ] write overhead impact reviewed
- [ ] index rollout plan documented
- [ ] startup index bootstrap (`ensure_indexes`) updated when new high-volume query paths are introduced
- [ ] explain-plan evidence captured for hot routes (no unintended `COLLSCAN` on large collections)

## 8.4 Data safety checks
- [ ] backup snapshot confirmed pre-release
- [ ] restore drill status current
- [ ] report artifact paths and permissions validated

---

## 9. Deployment Approval Workflow

## 9.1 Required approval roles
At minimum, each production release requires sign-off from:
- Engineering owner
- QA owner
- Operations/DevOps owner
- Security reviewer for security-impacting changes

## 9.2 Approval stages
1. **Technical readiness**: tests, docs, changelog complete.
2. **Operational readiness**: deployment and rollback prepared.
3. **Risk readiness**: known risks documented and accepted.
4. **Execution approval**: release window approved.

## 9.3 Approval evidence
Release ticket or change record must include:
- commit/tag reference
- test evidence summary
- migration summary
- rollback plan
- approver names/timestamps

## 9.4 Emergency release policy
Emergency releases may use accelerated approvals but must still include:
- minimal test evidence
- rollback plan
- post-release review

---

## 10. Rollback Policy
Rollback is a planned path and must be prepared before deployment begins.

## 10.1 Rollback triggers
- severe availability degradation
- critical security or authorization regression
- data integrity risk
- report generation failure affecting clinical workflow continuity

## 10.2 Rollback prerequisites
- previous stable image tag available
- previous config snapshot available
- compatibility of data state with rollback version reviewed

## 10.3 Rollback process
1. stop forward rollout
2. deploy prior stable images/config
3. validate health endpoints
4. validate critical workflows
5. record rollback event and rationale
6. open corrective follow-up plan

## 10.4 Rollback limitations
If release includes irreversible data changes without compatibility layer, code rollback may not fully restore expected behavior. For this reason, irreversible migrations must be gated more strictly and avoided unless operationally necessary.

---

## 11. Release Closure and Post-Release Review
Release is not complete at deploy time. Closure requires verification and record completion.

## 11.1 Closure checklist
- [ ] production smoke checks completed
- [ ] monitoring baseline reviewed
- [ ] no unresolved critical alerts
- [ ] release evidence archived
- [ ] stakeholders notified

## 11.2 Post-release review
For significant releases, conduct short review:
- what went well
- what failed or nearly failed
- which controls need improvement
- any policy updates required

---

## 12. Governance Anti-Patterns to Avoid
- releasing from unreviewed branch commits
- changing production config without trace record
- skipping compatibility checks for "small" DB changes
- tagging releases before final gate completion
- undocumented hotfix merges to protected branches

Each anti-pattern increases audit and operational risk.

---

## 13. Assumptions
ASSUMPTION:
- Git-based workflow with protected `main` branch is available.
- CI pipeline executes tests and produces quality artifacts.
- Release governance tooling (ticket/change record system) exists in organization.

---

## 14. Future Evolution Considerations
1. Add automated release checklists in CI/CD with policy gate enforcement.
2. Add machine-readable changelog linting for required sections.
3. Add automated compatibility verification suite for MongoDB 3.4 constraints.
4. Add signed release evidence bundles linking tag, artifacts, and approvals.
5. Add progressive delivery controls (canary/blue-green) with automatic rollback triggers.
