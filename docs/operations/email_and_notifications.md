# Email and notifications

## Delivery channels

| Event | Email | In-app behavior |
| --- | --- | --- |
| Local account invitation | Account setup link | Administrative workflow feedback |
| Local password reset | Reset link | Security notification to administrators |
| Password set or changed | Confirmation | Workflow feedback |
| Profile or account-status change | Account notification | Workflow feedback |
| Administrative broadcast | Generic notice linking to the inbox, when configured | Durable recipient-scoped message |
| Clinical-rule or catalog approval request/outcome | Not currently emailed | Durable workflow notification with a target link |

Authentication and account email uses the shared SMTP helper. Broadcast email is
delivered by Celery, not during the HTTP request. Its subject and body do not copy
broadcast text or clinical information; recipients must sign in to read the message.

All messages include an HTML alternative and plain text, the embedded Coyote3
logo, a severity badge, and an automated-message footer. No remote image request
is needed to display the logo. Non-production emails show the environment.
Supported severity labels are **INFO**, **IMPORTANT**, **WARNING**, **CRITICAL**,
and **SUCCESS**. Account-security messages use IMPORTANT; broadcast severity is
selected by the sender.

## Configuration

Configure the API and worker consistently with `SMTP_HOST`, `SMTP_PORT`,
`SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
`SMTP_USE_TLS`, and `SMTP_USE_SSL`. STARTTLS and implicit TLS are alternative
transport modes; use the one required by the relay. TLS certificates are verified.
`PUBLIC_BASE_URL` and `SCRIPT_NAME` must identify the externally reachable
application URL, including any deployment prefix.

| Setting | Development default | Purpose |
| --- | --- | --- |
| `SMTP_FROM_EMAIL` | `no-reply@coyote3.local` | Invitations and general account messages |
| `SMTP_SECURITY_FROM_EMAIL` | `security@coyote3.local` | Password and account-change notifications |
| `SMTP_INFO_FROM_EMAIL` | `info@coyote3.local` | Administrative broadcasts |

These mailboxes are unmonitored. Coyote3 sets automated-message headers and a
Reply-To address matching the sender, but cannot disable an email client's Reply
button or reject incoming mail itself. Configure inbound rejection or an appropriate
unmonitored-mailbox response on the mail server. Do not silently discard security
reports sent to an address users have been told is monitored.

Use relay-authorized addresses on a center-owned domain in production. The
`.local` suffix is [reserved for local name resolution](https://www.rfc-editor.org/rfc/rfc6762.html),
not a public mail domain. Authorize all three senders with the relay and configure
the center's SPF, DKIM, and DMARC policy as appropriate.

The worker and Celery beat must be running for broadcast email. Beat requests
delivery every 30 seconds; each execution processes up to ten recipients. The
broadcast response reports `email_state: pending` when email was queued, or
`not_configured` when SMTP or the public URL was unavailable. Neither status
proves delivery. Enabling SMTP does not email previously unqueued broadcasts.

Install declared MongoDB indexes before starting an updated API or worker. With
the target deployment environment loaded, run:

```bash
PYTHONPATH=. .venv/bin/python scripts/manage_mongo_indexes.py apply
```

The notification repository declares `email_deliveries_state` for queued delivery
lookup, alongside its existing recipient and expiry indexes.

Recipient state lives in `notifications.email_deliveries`. A worker atomically
claims a two-minute lease, rechecks the account's active state and email address,
and records `sent`, `failed`, or `skipped`. Expired leases can be reclaimed; after
three interrupted attempts the record becomes `unknown` for operator review.
Terminal failures are not automatically retried. SMTP acceptance and MongoDB
updates cannot form one transaction: a worker crash after acceptance can produce
a duplicate on retry. Inspect uncertain outcomes before manually resending.

## Broadcast lifecycle

The admin broadcast composer accepts Markdown using the same renderer as analysis
comments. Its Write and Preview modes support reviewing formatting before sending.
Raw HTML is escaped; links use the renderer's supported HTTP(S) syntax. Stored
message text remains Markdown, not pre-rendered HTML.

The tray shows a title and severity badge. Expanding a message reveals its body and
marks it read. Reading never withdraws a broadcast. Recipients cannot clear it,
including through the bulk-clear API. Only its sender can withdraw it for everyone.
The sender can review and withdraw messages under **Sent broadcasts**, even when
the sender was not a recipient. Withdrawal records the sender and timestamp and
emits `notification.broadcast.withdrawn` in the audit log.

An optional expiry is entered in the sender's local time and submitted as a
timezone-aware timestamp. Past or timezone-less values are rejected. Without an
expiry, a broadcast remains visible until withdrawn. Withdrawal and expiry hide
the message on inbox refresh, normally within 30 seconds, and stop new email claims.
Already accepted or in-flight SMTP delivery cannot be recalled.

| Stored field | Purpose |
| --- | --- |
| `is_broadcast` | Enforces sender-only withdrawal and excludes recipient clearing |
| `severity` | Semantic importance, independent of message category |
| `message` | Original Markdown body |
| `created_by`, `recipients` | Sender identity and recipient snapshot |
| `expires_on` | Optional visibility deadline; not a deletion timestamp |
| `withdrawn_on`, `withdrawn_by` | Sender-controlled withdrawal history |
| `read_by`, `dismissed_by` | Recipient read state and personal-message clearing |
| `email_deliveries` | Per-recipient SMTP delivery state |

Notification records are retained in MongoDB after expiry or withdrawal. They are
not removed by TTL or application cleanup. Plan storage retention and backups
accordingly. `NOTIFICATION_RETENTION_DAYS` supplies the visibility duration for
non-broadcast workflow messages; it does not expire new broadcasts. Personal
messages can still be cleared by their recipient without affecting anyone else.

### Existing installations

Stop notification producers and workers while changing the expiry index. With the
application's MongoDB environment loaded, run the dry run and then apply:

```bash
.venv/bin/python scripts/migrate_notification_retention.py
.venv/bin/python scripts/migrate_notification_retention.py --apply
PYTHONPATH=. .venv/bin/python scripts/manage_mongo_indexes.py apply
```

The migration replaces the `expires_on` TTL index with a normal index and marks
existing administrative broadcasts. It preserves bodies, recipients, read state,
and existing expiry dates. Already deleted records cannot be recovered by this
script. Index DDL runs outside transactions; document changes are transactional.
Re-running the migration is safe. Deploy the updated API, worker, and frontend
together; old code does not enforce the retained broadcast lifecycle.

## Local testing without an SMTP relay

[Mailpit](https://mailpit.axllent.org/docs/install/docker/) captures test messages
without forwarding them. Its SMTP port is 1025 and browser interface is 8025.
Use synthetic accounts and messages only.

Add the optional Compose override to the same deployment command and environment
file used for the application:

```bash
./scripts/compose-with-version.sh --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml \
  -f deploy/compose/docker-compose.mail.yml --profile mail up -d mailpit
```

For API and workers inside that Compose network, use:

```dotenv
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USE_TLS=0
SMTP_USE_SSL=0
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=coyote3@example.test
SMTP_INFO_FROM_EMAIL=info@example.test
SMTP_SECURITY_FROM_EMAIL=security@example.test
SMTP_FROM_NAME=Coyote3
```

For a host-run API, use `SMTP_HOST=127.0.0.1`. Recreate the API and worker with
the test settings, then open `http://127.0.0.1:8025`. Trigger an invitation or reset
for a synthetic account. Publish a broadcast to that account and check both the
in-app message and captured email, including the deployment prefix in the link.
The optional service binds published ports to loopback and configures no relay.
Do not use this capture service for production or real clinical messages.

Before production acceptance, separately verify connectivity from API and worker
containers, relay credentials and TLS, sender authorization, delivered messages,
and working links. A local capture test cannot establish production delivery.

## Automated checks

SMTP unit tests simulate acceptance and failures without delivering email. MongoDB
lease tests use a UUID-named disposable database and a mocked SMTP sender:

```bash
NOTIFICATION_TEST_MONGO_URI='mongodb://127.0.0.1:27017/?replicaSet=coyote3-rs' \
  .venv/bin/pytest -q --no-cov tests/integration/test_notification_email_delivery.py
```

The tests remove only their temporary database. They do not read deployment users
or messages. Keep credentials out of command history; provide a protected environment
variable when authentication is required.
