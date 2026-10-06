# Initial deployment checklist

Use this checklist to record completion of the [first installation procedure](first-installation.md).
It is an acceptance record, not a second sequence of deployment commands.
For an existing installation, use the upgrade or redeployment procedure instead.

## Host and deployment identity

- [ ] Reviewed release commit and container image identifiers recorded.
- [ ] Private environment file and center configuration location recorded and backed up.
- [ ] Compose project name and external application network recorded.
- [ ] MongoDB endpoints, replica-set readiness and four distinct database names verified.
- [ ] Existing knowledgebase data retained and reference versions reviewed.
- [ ] Data/log roots and container UID/GID verified; required runtime directories present.
- [ ] Center configuration and optional pipeline input mounts contain the expected files.
- [ ] Public origin, path prefix, listener scheme and TLS ingress match the browser URL.

## Bootstrap and accounts

- [ ] Database baseline completed without unresolved errors.
- [ ] Initial named administrator and emergency superuser have distinct identities.
- [ ] Both temporary passwords replaced and recovery ownership recorded.
- [ ] No demonstration center configuration is used for clinical work.
- [ ] Required MongoDB index plan reviewed and compatible missing indexes applied.

## Application and clinical configuration

- [ ] API and Redis healthy; all required services running without restart loops.
- [ ] UI, API health and documentation reachable through the intended public URL.
- [ ] Authentication, permission boundaries, workers and notification delivery verified.
- [ ] Assay groups, ASPs, subpanels, ISGLs and reporting rules reviewed before dependent ASPCs.
- [ ] Active ASPCs have the correct environment, enabled analyses, filters and report sections.
- [ ] Representative approved validation workflows completed with evidence retained.
- [ ] Report generation, saved reports, exports and audit events verified.
- [ ] Persistent data and database backups completed; isolated restore tested.
- [ ] Center release acceptance signed before clinical use.

Record operator, date, release, configuration revision, backup identifiers and
validation evidence in the center's deployment record. Store secrets and clinical
records outside Git. Use the [acceptance checklist](acceptance-checklist.md) for
the detailed clinical and operational evidence.
