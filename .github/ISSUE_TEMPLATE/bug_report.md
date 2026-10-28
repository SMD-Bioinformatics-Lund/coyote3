---
name: Bug report
about: Report an unexpected result, regression, or failed workflow
title: "[Bug]: "
labels: ["bug"]
assignees: ""
---

<!-- Search existing issues first and link a matching report rather than duplicating it.
Use synthetic examples. Never attach patient data, real sample identifiers, credentials,
session cookies, tokens, private URLs, or unredacted logs and screenshots.
Report vulnerabilities through SECURITY.md, not a public issue. -->

## Summary

Describe the affected workflow, what failed, and when it started. Use a specific
title, for example: "PDF export splits a variant table across pages".

## Impact and current status

- Affected users or workflow: <!-- Describe roles and scope without identifying people. -->
- Frequency: <!-- Every attempt, intermittent, or observed once. -->
- Operational impact: <!-- Blocked, degraded, or cosmetic; explain the consequence. -->
- Workaround: <!-- Describe it, or state that none is known. -->

## Steps to reproduce

Include prerequisites, relevant permissions, and the smallest synthetic example
that reproduces the problem. If it cannot be reproduced, describe the observations.

1. Start from ...
2. Perform ...
3. Observe ...

## Expected behavior

State the result you expected. Link the documented behavior when available.

## Actual behavior and evidence

State the actual result. Include the exact redacted error message, HTTP status,
or screenshot when relevant. For a failed API request, include the method, route,
approximate timestamp with time zone, and `X-Request-ID` or displayed support reference.

Use short, redacted excerpts instead of complete logs or data exports.

## Environment

- Coyote3 application version or commit:
- Environment: <!-- Production, staging, test, or local; no private hostnames. -->
- Browser and OS, or API client and version:
- Affected SDK or DNA/RNA report template version, if relevant:
- Relevant role, permission, or non-sensitive configuration:

## Regression and investigation

- Last known working version: <!-- If known. -->
- Recent related changes: <!-- Upgrade, configuration, browser, or deployment change. -->
- Checks already performed and their results:
- Related issues or pull requests:

Separate confirmed observations from suspected causes. Write "unknown" where
information is unavailable.
