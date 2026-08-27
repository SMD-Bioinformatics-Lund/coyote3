# Target-center acceptance

Target-center acceptance verifies the deployed release against the center's
network, identity provider, representative synthetic data, and recovery
infrastructure. It is performed in a validation environment before production
promotion. Credentials, manifests, clinical files, and evidence remain in the
center's controlled systems and are never committed to the repository.

## Acceptance inputs

Prepare the following before starting:

| Input | Requirement |
| --- | --- |
| Release | Exact application version and image digest proposed for production |
| Environment | Validation env file, Compose profile, public HTTPS URL, and `SCRIPT_NAME` |
| Accounts | Local administrator, restricted clinical reviewer, and LDAP test account when LDAP is enabled |
| DNA case | Approved synthetic or de-identified manifest with the DNA analyses used by the center |
| RNA case | Approved synthetic or de-identified manifest with the RNA analyses used by the center |
| Recovery target | Empty, isolated MongoDB instance or database that cannot affect the source environment |
| Evidence location | Controlled ticket, validation record, or quality-management system |

## 1. Validate configuration

Run preflight against the exact files used for deployment:

```bash
PYTHON_BIN=.venv/bin/python scripts/center_preflight.sh \
  --env-file .coyote3_validation_env \
  --compose-file deploy/compose/docker-compose.yml \
  --compose-file deploy/compose/docker-compose.stage.yml
```

The command must validate secrets, render Compose, confirm database-name
consistency, and verify that the container UID/GID can write to the configured
data and log roots. Record the complete output.

## 2. Validate reverse-proxy routing

Use the public URL; do not test this stage through an internal container port.
For a deployment at `https://validation.example.org/coyote3`, verify:

```bash
curl -fsSI https://validation.example.org/coyote3
curl -fsSI https://validation.example.org/coyote3/
curl -fsS  https://validation.example.org/coyote3/api/v1/health
curl -fsSI https://validation.example.org/coyote3/docs-site/
curl -fsSI https://validation.example.org/coyote3/api/v1/docs
curl -fsSI https://validation.example.org/coyote3/public
```

Both prefix forms must reach Coyote3, generated links must retain the prefix,
and no response may expose or redirect to an internal host or port. Confirm the
TLS certificate, `Content-Security-Policy`, `X-Content-Type-Options`, and
`X-Frame-Options` headers in the browser network inspector or with `curl -I`.

## 3. Validate authentication providers

Test each configured provider independently:

| Test | Expected result |
| --- | --- |
| Valid local account | Login succeeds; profile and permissions match the database account |
| Invalid local password | Login fails without identifying whether the account exists |
| Valid LDAP account | Login succeeds and resolves the intended local role/group mapping |
| Invalid LDAP password | Login fails without creating or changing a local account |
| LDAP unavailable | Local login remains usable; LDAP login reports a provider-specific service error |
| Restricted account | Protected admin routes return `403`; permitted clinical routes remain available |
| Logout | Server session is revoked and the browser returns to the login page |

Use `scripts/api_login.py` for an API-level local-provider check and complete
the LDAP and browser-session checks through the public reverse proxy. Store
credentials in the shell or the center's secret runner, never in command files
or screenshots.

## 4. Validate representative DNA and RNA ingestion

Run each controlled manifest through the deployed API:

```bash
bash scripts/center_check.sh \
  --api-base-url https://validation.example.org/coyote3 \
  --username "$COYOTE3_VALIDATION_USER" \
  --password "$COYOTE3_VALIDATION_PASSWORD" \
  --yaml-file /validation-data/dna/sample.coyote3.yaml

bash scripts/center_check.sh \
  --api-base-url https://validation.example.org/coyote3 \
  --username "$COYOTE3_VALIDATION_USER" \
  --password "$COYOTE3_VALIDATION_PASSWORD" \
  --yaml-file /validation-data/rna/sample.coyote3.yaml
```

Then run the real-browser suite:

```bash
export COYOTE3_E2E_BASE_URL='https://validation.example.org/coyote3/'
export COYOTE3_E2E_USERNAME="$COYOTE3_VALIDATION_USER"
export COYOTE3_E2E_PASSWORD="$COYOTE3_VALIDATION_PASSWORD"
export COYOTE3_E2E_DNA_SAMPLE='DNA_VALIDATION_001'
export COYOTE3_E2E_RNA_SAMPLE='RNA_VALIDATION_001'
npm --prefix frontend run test:e2e:real
```

For each sample, compare loaded resources, finding counts, enabled tabs,
filters, report preview, and audit events with the approved validation record.
A skipped authenticated browser test is incomplete evidence, not a pass.

## 5. Validate backup restoration

Create an archive from the validation source:

```bash
scripts/mongo_backup_archive.sh \
  --mongo-uri "$COYOTE3_BACKUP_MONGO_URI" \
  --out-dir /secure-backups/coyote3 \
  --label release-candidate
```

Verify the generated checksum metadata, then restore into the isolated recovery
target only:

```bash
scripts/mongo_restore_archive.sh \
  --mongo-uri "$COYOTE3_RECOVERY_MONGO_URI" \
  --archive /secure-backups/coyote3/<archive>.archive.gz \
  --drop \
  --confirm RESTORE_PATIENT_DATA
```

After restoration, compare collection counts and representative ASP, ASPC,
ISGL, sample, annotation, report, notification, and audit records. Start a
temporary application instance against the recovery URI and repeat login,
sample opening, and report-preview checks. Never rehearse restoration against
the source database.

## 6. Record the decision

The acceptance record must include:

- application version, Git revision, and container image digests
- environment and public URL, excluding credentials
- DNA and RNA validation fixture revisions
- authentication-provider results and tested roles
- browser-suite and preflight output
- backup archive identifier, checksum, recovery target, and restore result
- deviations, risk owner, approver, and promotion decision

Production promotion is blocked when a failure affects authentication,
authorization, finding visibility, ingest atomicity, report output, auditability,
reverse-proxy routing, or restoration.
