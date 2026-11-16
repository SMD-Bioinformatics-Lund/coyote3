# Core architecture

Domain modules own clinical decisions and repository protocols. Application
services coordinate use cases using explicit host-supplied capabilities.
Pydantic contracts validate inputs and portable records. Configuration modules
own software defaults and explicit immutable center-profile selection.

The core imports no API application, MongoDB driver, Celery, Redis or remote HTTP
client. Database adapters compile logical selections and provide transactional
persistence. A future adapter must preserve identity, missing/null, filtering,
concurrency and snapshot semantics; a connection-string change is insufficient.

Report JSON is rendered by `smd-reports` using the existing `coyote3` preset.
Report wording, finding eligibility, rule publication and saved provenance stay
governed by core operations. Database-specific audit hashing is supplied by hosts.

`application/operations/administration/` groups services by the resource they manage.
Clinical-rule authoring composes scope validation, reviewer assignments, record
transitions and lifecycle services in `application/reporting/clinical_rules/authoring/`.
`DnaReportBuilder` in `application/reporting/dna/` assembles evidence and snapshots;
`ReportDocumentBuilder` in `application/reporting/document/` composes presentation sections.
Each report build uses fresh state. Changes to any document-builder module change
the renderer fingerprint checked when a reviewed preview is saved.

Ingestion services own parsing, validation, fenced job execution and stable manifest
acknowledgement. Hosts supply an authorized executor, durable job repository,
transaction completion callback, retry classification and audit delivery. Celery
registration, database wiring and process configuration stay outside core.

Core also packages canonical permission/role definitions and VEP grouping policy.
Reading them does not install data. Hosts own reference snapshots, explicit
installation and deployment-specific accounts and grants.

Package tests cover standalone behavior. Repository-wide integration tests cover
the core together with adapters, authentication, workers and the API.
