<!-- Pull Request Template — Coyote3 -->

# Summary
Clearly describe the purpose of this PR and what changed.  
If it fixes an issue, reference it (e.g., Fixes #123).  
For reviewers: include how to test this change (steps, routes, sample data, expected outcomes).  

---

## Type of change
- [ ] Bug fix  
- [ ] Patch / hotfix  
- [ ] New feature / enhancement  
- [ ] New route / endpoint  
- [ ] Refactor / cleanup  
- [ ] UI/UX update  
- [ ] Documentation update  
- [ ] Infrastructure / CI/CD 

---

## Checklist (author)

### General
- [ ] **CHANGELOG** updated with a clear entry  
- [ ] **Version bumped** (if user-facing change)  
- [ ] Unit tests / integration tests added or updated  
- [ ] Affected routes tested in dev/stage with real data  
- [ ] Outputs verified (UI pages, DB writes, logs, etc.)  
- [ ] Documentation updated (developer + user docs if applicable)  
- [ ] At least one reviewer has tested and approved the code 

Provide additional details or clarify missing information in the **Summary** section.  

---  

### Schemas & Backward Compatibility
- [ ] No schema changes  
- [ ] User schema updated and migration path documented  
- [ ] Role/permission schema updated (permission policies, roles, deny_permissions)  
- [ ] Assay config (ASP, ASPC) schema updated with defaults validated  
- [ ] ISGL (In Silico Genelist) schema updated and validated  
- [ ] Schema backward compatibility tested (old documents still valid)  
- [ ] Changelog/history for versioned documents preserved and restorable  
- [ ] Validation enforced via `store.schema_handler`  

Provide additional details or clarify missing information in the **Summary** section.  

---  

### Routes & Functionality
- [ ] New route introduced documented (path, params, permissions)  
- [ ] Route-level permission declared (`@require("permission")` or `min_role`)  
- [ ] Input validated (forms, JSON, query params)  
- [ ] Proper error handling and user feedback added  
- [ ] Access control verified (admin, developer, tester, manager, user, viewer, external)  
- [ ] Pagination/filters implemented for list views (if applicable)  
- [ ] Performance tested (indexes, DB hits count, caching)  

Provide additional details or clarify missing information in the **Summary** section.  

---  

### Security & Permissions
- [ ] No new permissions  
- [ ] New permission policy added in `permission_policies` collection  
- [ ] Role documents updated with new permissions/denies (priority preserved)  
- [ ] RBAC hierarchy verified (admin > developer > manager > user > viewer > external)  
- [ ] Route metadata checked against permission model  
- [ ] Personal Identifiable Information minimized/redacted in logs and UI  

Provide additional details or clarify missing information in the **Summary** section.  

---  

### Caching & Consistency
- [ ] No caching changes  
- [ ] Cache invalidated on create/update/delete (samples, configs, dashboards)  
- [ ] Avoids stale data in sample/variant views  
- [ ] New functionality added to persistent **DB hits counter** if applicable  

Provide additional details or clarify missing information in the **Summary** section.  

---  

### Logging & Auditing
- [ ] Centralized logger used (UTC daily rotation)  
- [ ] Sensitive data not logged  
- [ ] Audit logging via `AuditLogger` for create/update/delete/toggle actions  
- [ ] Reviewer verified audit log output in `logs/YYYY/MM/DD/*.log`  

Provide additional details or clarify missing information in the **Summary** section.  

---  

### UI/UX
- [ ] Tailwind layout consistent with shared layout  
- [ ] Responsive across devices  
- [ ] Loading/empty/error states handled  
- [ ] Tooltips/help text for new controls added  
- [ ] Print/export mode tested (assay config, user view, role view) 

Provide additional details or clarify missing information in the **Summary** section.  

---  

## Breaking changes
- [ ] No breaking changes  
- [ ] Database schema/collection updated (migration steps documented)  
- [ ] API routes or response structure changed (migration path documented)  
- [ ] Config variables/env keys changed (defaults & rollout documented)  
- [ ] UI workflows changed (user/analyst/admin impact documented)  

---

## Testing performed
Describe what was tested, datasets/profiles used, and results.  
Attach logs, screenshots, or query outputs if helpful.  

Performed by:  
- [ ] Ram  
- [ ] Viktor  
- [ ] Sailedra  
- [ ] (Add if missing)

---

## Notes for reviewers
List risk areas, edge cases, or things needing extra attention.  
Examples:  
- New schema migration (users, assay configs, ISGLs)  
- Route-level permission correctness  
- Cache invalidation (done samples, dashboard stats)  
- Assay config backward compatibility  
- Atomic sample ingestion (sample + variants + CNVs + coverage)  

---

## Review performed by
- [ ] Ram  
- [ ] Viktor  
- [ ] Sailedra  
- [ ] (Add if missing)

---

## Release notes (draft)
Short, user-facing bullet points for the next release tag.  
Focus on features, fixes, or improvements that clinicians, analysts, or admins will notice.

