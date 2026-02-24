# Technical Debt and Refactor Roadmap

This chapter defines the planned engineering improvements required to keep Coyote3 maintainable, auditable, and predictable as scope grows.

## Purpose

The roadmap exists to reduce risk in three areas:

- interpretation reproducibility
- configuration safety
- long-term code maintainability

## Current technical debt

Coyote3 currently carries debt in the following areas.

Interpretation state remains partly mutable at case level. This is practical for active work but can make historical reconstruction harder if report-linked context is not treated as the source of truth.

Annotation data includes both older and newer scope models. The application handles this correctly, but mixed structure increases matching complexity and maintenance cost.

Some blueprint modules still carry orchestration and business rules together. This slows feature delivery, complicates testing, and increases regression risk.

Configuration versioning exists, but critical runtime paths still depend primarily on mutable “current” records rather than immutable version references.

## Target architecture

The target state is:

- immutable report context at report save time
- deterministic annotation identity and scope model
- versioned configuration with clear current pointers
- thin route handlers and service-layer orchestration
- explicit operational guardrails (indexes, logging, migration discipline)

## Workstream 1: report reproducibility hardening

The goal is to ensure every saved report can be reconstructed exactly from stored context.

Current `reported_variants` behavior is already the foundation. The next step is to persist complete report context metadata together with report identity, including resolved configuration identity and effective filters used at generation time.

Outcome: report-time truth becomes independent of future sample/filter/config changes.

## Workstream 2: configuration version model hardening

Configuration should evolve through explicit versions, with clear distinction between active version and historical versions.

Recommended model:

- small “current pointer” record per logical entity
- immutable full version records
- optional change-diff metadata for UI and audit readability

Outcome: rollback, audit, and release reproducibility become operationally safe and simple.

## Workstream 3: annotation model normalization

Annotation records should converge on a single deterministic identity-and-scope contract.

Required direction:

- canonical identity key
- explicit scope semantics (global, assay, assay+subpanel)
- explicit record kind (class/text)

Migration should preserve legacy compatibility while moving matching logic to strict-scope-first with controlled fallback behavior.

Outcome: predictable matching behavior, easier debugging, and lower maintenance complexity.

## Workstream 4: service-layer extraction

Business orchestration should move from large route modules into dedicated services.

Primary extraction targets:

- sample workflow orchestration
- annotation classification orchestration
- report assembly and persistence orchestration

Outcome: smaller route handlers, clearer responsibilities, easier test onboarding, and lower change risk.

## Workstream 5: operational resilience

Core hardening tasks:

- enforce required unique and performance indexes
- improve structured logging around report and interpretation actions
- standardize migration process with dry-run and rollback documentation

Outcome: fewer production surprises and faster operational troubleshooting.

## Delivery plan

Priority order:

1. report reproducibility hardening
2. configuration version model hardening
3. annotation model normalization
4. service-layer extraction
5. operational resilience hardening

## Completion criteria

This roadmap is complete when:

- report reconstruction is deterministic from stored report context
- configuration rollback is pointer-based and audit-safe
- annotation matching behavior is deterministic and model-consistent
- core workflows run through service-layer orchestration
- migration and operations playbooks are stable and repeatable
