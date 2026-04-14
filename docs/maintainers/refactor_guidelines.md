# Engineering and Refactoring Standards

This document establishes the binding architectural requirements and engineering guidelines required when modifying, refactoring, or optimizing any application logic within the platform. All maintenance strategies must strictly prioritize deployment stability, contract adherence, and absolute security policy enforcement.

## Fundamental Engineering Goals

All modifications delivered to the core codebase must satisfy the following technical prerequisites:
- Deliver measurable improvements to code maintainability and execution clarity.
- Systematically eliminate structural duplication without circumventing or mutating original execution behavior.
- Enforce explicit isolation boundaries separating Presentation logic (UI), Data Access capabilities, and Core API rule abstractions globally.

## Non-Negotiable Contract Requirements

Code modifications are forbidden from altering foundational security constraints or implicit access boundaries:
- Implementation of hidden compatibility layers or undocumented middleware bridging APIs is fundamentally prohibited.
- Endpoints shall not silently mutate outbound or inbound structural data layouts unless officially documented via Pydantic model version bumps.
- Request interceptor policies and role-based access checks (RBAC) must remain visibly intact and strictly evaluated against original coverage paths.
- Mandatory database validation schemes and payload validation pipelines must be enforced prior to dispatching operational writes to persistent endpoints.

## Executable Modification Lifecycle

All system refactoring workflows are required to proceed through a sequential validation process:

1. **Verify Baseline State:** Architect and pass determinable state tests validating the functionality of the precise route or logic function awaiting alteration.
2. **Isolate Seams:** Implement changes compartmentalizing independent system domains iteratively (Example: Segmenting route parameters, then testing service classes, and finally data connection layers individually).
3. **Continuous Execution Checking:** Execute continuous component-specific analytical tests directly after securing individual infrastructure seams successfully.
4. **Final Acceptance Validation:** Pass all systemic linting gates, typing boundaries, end-to-end containerized pipelines, and holistic test boundaries natively before proposing production readiness.

## Prohibited Operational Anti-Patterns

Engineering PRs will be systematically rejected if any implementations fall into the following restricted practices:

- Embedding dynamic database commands, algorithmic decisions, or heavy rule manipulations natively within UI templates or Presentation domains natively.
- Eliminating required application perimeter permissions in favor of convenience functions inside REST layers.
- Running incomplete backend operations inside transactional contexts without proper rollback behavior.
- Using untargeted or unbounded global exception handlers (`except Exception`) that inherently swallow application state failure logging implicitly in background processes natively.
