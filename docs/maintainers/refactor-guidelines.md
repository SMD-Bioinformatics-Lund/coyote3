# Refactor Guidelines

## Goals

- improve readability and maintainability
- reduce duplication without changing behavior
- preserve explicit boundaries between UI, API, and data access

## Rules

- no hidden compatibility shims unless explicitly approved
- no silent data-shape changes at API boundaries
- keep security checks intact
- enforce DB contract validation where writes occur

## Safe refactor pattern

1. snapshot current behavior with tests
2. refactor one seam at a time (router -> service -> core)
3. run targeted tests after each seam
4. run full lint/test/gates before finalizing

## Anti-patterns to avoid

- moving business rules into templates/UI views
- bypassing permission checks in convenience paths
- introducing partial writes without rollback/cleanup
- broad try/except blocks that swallow logic errors
