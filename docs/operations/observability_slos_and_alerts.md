# Observability SLOs And Alerts

This guide turns Coyote3 auth/mail telemetry into practical SLO dashboards and alert rules.

## Telemetry signals available now

The API emits structured log lines with stable prefixes:

- `auth_metric ...`
- `mail_metric ...`

Operational state is also available to authorized administrators on
**Admin > Application Controls**. The page combines configured task/module
switches with a live Celery control-inspection response:

| Runtime field | Meaning | Interpretation |
| --- | --- | --- |
| Status | Whether at least one Celery worker replied to inspection. | `online` means a worker answered; it is not a proof that every task can complete. |
| Workers | Number of responding worker nodes. | Zero or `unavailable` requires worker/broker investigation. |
| Active | Tasks currently executing. | Sustained growth can indicate slow processing or blocked workers. |
| Reserved | Tasks received by workers but not executing. | Sustained growth indicates queue pressure or insufficient concurrency. |
| Scheduled | Worker-side ETA/countdown tasks. | This is distinct from periodic Beat entries. |
| Registered | Unique task names advertised by responding workers. | Confirms worker image/task registration consistency. |
| Beat entries | Periodic tasks configured in the active Celery application. | Confirms configured schedule only; inspect task history/audit records to prove execution. |
| Queues | Queues reported by active workers. | Confirms worker consumption topology. |

!!! warning "Configured versus observed state"

    Application Controls can prevent new task-family executions. They do not
    stop already-running tasks, and an enabled switch does not prove a worker,
    broker, file mount, or external dependency is healthy. Use both the
    configured controls and observed runtime state during incident response.

Primary emitters:

- `api/security/auth_service.py`
- `api/security/password_flows.py`
- `api/infra/notifications/email.py`

## Recommended SLOs

Use these as baseline targets per center, then tune with real traffic:

1. Login success rate (excluding unknown/inactive users): `>= 99.0%` over 15 minutes.
2. Password token consumption success (invite/reset): `>= 98.0%` over 60 minutes.
3. Mail delivery success (`mail_metric send_result`): `>= 95.0%` over 60 minutes.
4. Mail fallback rate (`send_skipped` or `send_result outcome=failed`): `<= 5.0%` over 60 minutes.

## Dashboard panels

Build at least these panels:

1. `auth_metric login_attempt` count by `outcome` and `auth_type`.
2. `auth_metric password_token_issue` and `password_token_consume` by `purpose` and `outcome`.
3. `auth_metric password_change` success/failure trend.
4. `mail_metric send_attempt` by host/from.
5. `mail_metric send_result` split by `outcome`.
6. `mail_metric send_skipped` by `reason`.

## Alert rules (provider-agnostic logic)

Use your log platform query language (Loki, Elasticsearch, Splunk, etc.) to implement equivalent rules:

1. `LoginSuccessDegradation`: login success ratio < 99% for 15 minutes.
2. `TokenConsumeFailureSpike`: token consume failures > 5 in 10 minutes.
3. `MailDeliveryDegradation`: mail send success ratio < 95% for 30 minutes.
4. `MailDeliveryUnavailable`: any `send_skipped reason=smtp_not_configured` in production.
5. `CeleryWorkerUnavailable`: no worker replies to inspection for five minutes.
6. `CeleryQueueBacklog`: reserved task count grows for 15 minutes without a
   corresponding active-task increase.
7. `IngestFailureBurst`: two or more `ingest.watch.failed` or
   `ingest.bundle.failed` audit events within 15 minutes.
8. `MaintenanceFailure`: a scheduled maintenance task fails or no successful
   retention maintenance evidence appears within the expected nightly window.

Severity guidance:

- `warning`: short-lived ratio dips.
- `critical`: sustained delivery/auth degradation or hard configuration gaps in prod.

## Loki-style query examples

If you use Loki/Grafana, these examples can be adapted directly:

```logql
sum(rate({container="coyote3_api"} |= "auth_metric" |= "metric=login_attempt" |= "outcome=success"[5m]))
/
sum(rate({container="coyote3_api"} |= "auth_metric" |= "metric=login_attempt"[5m]))
```

```logql
sum(rate({container="coyote3_api"} |= "mail_metric" |= "metric=send_result" |= "outcome=success"[15m]))
/
sum(rate({container="coyote3_api"} |= "mail_metric" |= "metric=send_result"[15m]))
```

## Operational guide links

When an alert fires:

1. Validate runtime config in the active env file (`SMTP_*`, `PUBLIC_BASE_URL`) and confirm Redis connectivity from the API container.
2. Check API logs for recent `mail_metric` and `auth_metric` spikes.
3. Confirm connectivity to SMTP relay/host from API container network.
4. Verify fallback behavior in UI/admin flows (warning + manual setup URL still present).
5. Document incident + center-specific thresholds update if needed.
6. For Celery issues, compare the Application Controls runtime view with
   `docker compose ps`, worker/Beat logs, broker connectivity, and the
   internal task-status endpoint for a known task id.

## Ownership

- Platform/DevOps: dashboard and alert wiring.
- Application maintainers: metric schema stability and release notes.
- Center admins: SMTP endpoint correctness and on-call response.
