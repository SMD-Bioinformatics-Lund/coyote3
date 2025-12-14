# Encryption & Secrets

- **Fernet** key (`COYOTE3_FERNET_KEY`) is loaded in `config.py` for symmetric encryption needs
  (e.g., storing versioned payloads or sensitive fields).
- Avoid storing encryption keys in the database; inject via env/secret store.
- For document versioning, store **delta or full copies** and encrypt if they contain sensitive data.

Also see logging retention and data retention policies in Admin/Ops docs.
