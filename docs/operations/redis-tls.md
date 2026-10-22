# Production Redis transport encryption

Use verified TLS for the production cache, Celery broker and result backend.
Development and staging use the base Redis configuration without certificates; do not add
the TLS overlay to their Compose commands or environment files.

For production, add `deploy/compose/docker-compose.redis-tls.yml` after the base Compose
file and any production overrides. This overlay disables Redis's plaintext listener, retains password
authentication and mounts only the public CA certificate into application services.
It does not create or change host networks, firewall rules or published Redis ports.

## Create the certificates

If your organization supplies certificates, request a server certificate with `DNS:redis`
in its subject alternative names and `serverAuth` extended key usage. Otherwise, the
following OpenSSL commands create a private certificate authority (CA) and a Redis server
certificate. No public domain or browser certificate is needed for the internal `redis`
hostname. Run this once on a trusted administrator machine with OpenSSL installed, outside
the repository. These commands create new keys; do not rerun them over existing keys.

```bash
mkdir -p "$HOME/.local/share/coyote3/redis-ca"
chmod 700 "$HOME/.local/share/coyote3/redis-ca"
(
  cd "$HOME/.local/share/coyote3/redis-ca" || exit 1
  umask 077
  openssl genrsa -aes256 -out ca.key 4096
  openssl req -x509 -new -sha256 -days 3650 -key ca.key -out ca.crt \
    -subj '/CN=Coyote3 production Redis CA' \
    -addext 'basicConstraints=critical,CA:TRUE' \
    -addext 'keyUsage=critical,keyCertSign,cRLSign'
  openssl genrsa -out server.key 3072
  openssl req -new -key server.key -out server.csr -subj '/CN=redis'
  cat > server.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:redis
EOF
  openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days 365 -sha256 -extfile server.ext
  openssl verify -CAfile ca.crt -purpose sslserver -verify_hostname redis server.crt
)
```

OpenSSL prompts for a passphrase to protect `ca.key`, then asks for it when signing.
Keep that passphrase and CA private key in protected administrator storage for renewal;
never mount `ca.key` into a container. The server key is unencrypted so Redis can start
unattended; its host filesystem permissions provide access control.

## Pass the certificates to production

Copy only `ca.crt`, `server.crt` and `server.key` securely to the production host. The
following example assumes they were created on that host in the directory above. Run
these commands from the repository root. The UID/GID lookup uses the same Redis image as
the base stack and runs with networking disabled.

```bash
redis_tls_uid=$(docker run --rm --network none --entrypoint id redis:7.4.3 -u redis)
redis_tls_gid=$(docker run --rm --network none --entrypoint id redis:7.4.3 -g redis)
sudo install -d -m 750 -o root -g "$redis_tls_gid" /etc/coyote3/redis-tls
sudo install -m 644 "$HOME/.local/share/coyote3/redis-ca/ca.crt" /etc/coyote3/redis-tls/ca.crt
sudo install -m 644 "$HOME/.local/share/coyote3/redis-ca/server.crt" /etc/coyote3/redis-tls/server.crt
sudo install -m 600 -o "$redis_tls_uid" -g "$redis_tls_gid" \
  "$HOME/.local/share/coyote3/redis-ca/server.key" /etc/coyote3/redis-tls/server.key
```

For rootless Docker or user-namespace remapping, use the mapped host Redis identity for
ownership instead. Do not make the private key world-readable to work around access errors.

Add this setting to your **production** environment file:

```dotenv
COYOTE3_REDIS_TLS_DIR=/etc/coyote3/redis-tls
```

Keep the existing `REDIS_PASSWORD`. The overlay supplies the verified `rediss://` URLs
automatically, mounts the CA into API/both workers/beat/monitor, and mounts the server certificate
and key only into Redis. Do not commit certificates, private keys or environment files.
Missing source files fail deployment instead of creating empty host directories.

For the production installer, include the overlay in its Compose selection (plus any
other normal production installer options). Replace `coyote3-prod` below with your existing
production Compose project name and use that same name for every command; changing it
selects a different stack and different project-scoped volumes.

```bash
./scripts/deployment/install_center.sh \
  --env-file /path/to/production.env \
  --project coyote3-prod \
  --compose-file deploy/compose/docker-compose.yml \
  --compose-file deploy/compose/docker-compose.redis-tls.yml
```

For subsequent production Compose commands:

```bash
./scripts/deployment/compose-with-version.sh \
  --env-file /path/to/production.env \
  -p coyote3-prod \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.redis-tls.yml \
  up -d
```

Use the same overlay for installation containers and every subsequent Compose command.
Enabling it on an existing production stack recreates Redis and its clients; schedule a
maintenance window. Development and staging commands remain unchanged.

## Verify and renew

After starting production, check the authenticated TLS connection:

```bash
./scripts/deployment/compose-with-version.sh \
  --env-file /path/to/production.env \
  -p coyote3-prod \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.redis-tls.yml \
  exec -T redis redis-cli --tls --cacert /run/redis-tls/ca.crt --sni redis -h redis ping
```

Expect `PONG`; `REDISCLI_AUTH` is already supplied by the base Compose configuration.
Also verify API readiness and a worker task through your normal deployment checks: Redis's
own health check alone does not establish connectivity from application containers.

Applications require a trusted CA and verify the Redis hostname. Client certificates are
not required; clients authenticate using the existing `REDIS_PASSWORD`. Rotate the server
certificate before expiry and recreate Redis and its clients during a planned maintenance
window. Sign a new server CSR using the existing CA and the same extensions, replace the
server certificate/key with the permissions above, then run the production Compose command
with `up -d --force-recreate redis api worker maintenance-worker beat monitor`
so bind mounts use the new files.
Redis persistence remains on the existing data volume. Check the certificate expiry with:

```bash
openssl x509 -in /etc/coyote3/redis-tls/server.crt -noout -dates
```

The base configuration continues to use authenticated plaintext on its private network.
The TLS overlay must be selected to encrypt that transport. Certificate provisioning and
rotation belong to the deploying center. See the
[Redis TLS reference](https://redis.io/docs/latest/operate/oss_and_stack/management/security/encryption/)
for certificate and protocol requirements.
