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

Package tests cover standalone behavior. Repository-wide integration tests cover
the core together with adapters, authentication, workers and the API.
