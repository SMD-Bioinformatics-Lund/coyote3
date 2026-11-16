# Use the core in the application

The `coyote-core` library owns clinical operations and contracts. The API and
workers provide its runtime capabilities; the MongoDB adapter provides persistence.

Use the package-owned [core guide](../../core/docs/README.md) for installation,
use, configuration, reference and development. The application integration
contract is described in [application operations](application-sdk.md) and
[host trust](permissions.md).

## Application responsibilities

The API selects the reviewed center profile before importing clinical contracts.
It supplies current authenticated identities, assay/environment scope and service
factories. Workers use the restricted capabilities appropriate to their jobs.

The core does not choose deployment endpoints, load API secrets or provision
storage. Installing it does not replace persisted assays, users, gene lists or
published clinical rules.

Application releases select a tested core, MongoDB adapter and API combination.
See [package boundaries](package-boundaries.md),
[editable workspace development](uv-development.md) and
[release compatibility](compatibility.md). Package changes are recorded in the
[core changelog](../../core/CHANGELOG.md).
