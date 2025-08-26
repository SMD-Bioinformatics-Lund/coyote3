# Testing Strategy

- Unit tests for handlers and utilities.
- Integration tests for blueprint routes (auth required paths).
- **Coverage & mutation testing** recommended (pytest‑cov, mutatest).
- Use seed data and fixtures for samples/assays to make pages render.

CI can run linters (flake8/ruff), mypy, tests, and a link‑checker for docs.
