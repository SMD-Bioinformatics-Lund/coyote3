# MongoDB adapter contracts

Dependencies point from this adapter to `coyote-core`. Host composition supplies
configuration, logging, optional caches and operation-observation callbacks.
There are no API imports or HTTP-framework requirements.

Repository methods implement the operations consumed by core services. Record
codecs convert provider identities and dates at this boundary; driver result
objects are projected into core operation contracts. Selection compilation
belongs here, including array correlation and missing/null behavior.

The adapter owns collection names, indexes, connection-pool defaults, atomic
revision checks and transactional audit outboxes. The host reuses these defaults
before applying deployment settings; it does not redefine them.

Database transactions cannot make filesystem writes atomic. Report persistence
retains the existing pending-artifact and recovery flow. Retryable transaction
callbacks must not send messages, change files or perform external side effects.

Changes must preserve existing identity, query, snapshot and audit behavior.
Run the package tests and affected application integration tests. Validate real
transaction behavior against a separately authorized synthetic replica set;
mocked tests do not establish those guarantees.
