# API Reference And Workflows

## Route families

Main route modules under `api/routers/`:

- `auth.py`
- `samples.py`
- `small_variants.py`
- `cnvs.py`
- `translocations.py`
- `fusions.py`
- `biomarkers.py`
- `reports.py`
- `users.py`, `roles.py`, `permissions.py`
- `dashboard.py`, `coverage.py`, `public.py`
- `internal.py`

## Health check

```bash
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_API_PORT:-5818}/api/v1/health"
```

## Common workflow patterns

### Fetch sample and related findings

1. resolve sample via samples endpoint
2. query variant/cnv/translocation/fusion endpoints with sample id
3. fetch report metadata

### Update findings

1. send action/classification/comment payload
2. enforce permission gate
3. persist to target collection + annotation/audit as needed

## API development checklist

1. Add contract models (`api/contracts`)
2. Add/modify router endpoint
3. Implement service logic
4. Add tests in `tests/api` and `tests/unit`
5. Ensure lint and quality gates pass
