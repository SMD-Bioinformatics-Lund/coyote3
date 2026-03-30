# Observability SLOs And Alerts

This guide turns Coyote3 auth/mail telemetry into practical SLO dashboards and alert rules.

## Telemetry signals available now

The API emits structured log lines with stable prefixes:

- `auth_metric ...`
- `mail_metric ...`

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

1. Validate runtime config in active env file (`SMTP_*`, `WEB_APP_BASE_URL`, `CACHE_*`).
2. Check API logs for recent `mail_metric` and `auth_metric` spikes.
3. Confirm connectivity to SMTP relay/host from API container network.
4. Verify fallback behavior in UI/admin flows (warning + manual setup URL still present).
5. Document incident + center-specific thresholds update if needed.

## Ownership

- Platform/DevOps: dashboard and alert wiring.
- Application maintainers: metric schema stability and release notes.
- Center admins: SMTP endpoint correctness and on-call response.
