# Monitoring & Health

## Logs
- Centralized in `logs/YYYY/MM/DD/{date}.{level}.log` (see `logging_setup.py`).
- App attaches Gunicorn handlers in `run.py`.  
- Audit logs: actions decorated with `@log_action` write structured entries.

## Metrics
- Add log‑based metrics or integrate with your APM (e.g., request latency, DB hits).

## Health checks
- Implement a lightweight `/healthz` route if deploying behind a load balancer.
