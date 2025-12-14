# Key Sequences

## Login (LDAP or local)
```mermaid
sequenceDiagram
  participant U as User
  participant W as Flask App
  participant L as LDAP
  U->>W: POST /login (credentials)
  W->>L: Bind & verify (if LDAP)
  L-->>W: OK / Fail
  W-->>U: Session cookie; redirect
```

## Open sample → DNA view
```mermaid
sequenceDiagram
  participant U as User
  participant W as common_bp
  participant D as dna_bp
  participant S as SamplesHandler
  U->>W: GET /sample/<id>
  W->>S: get_sample_by_id(id)
  W->>D: redirect to dna_bp.list_variants
  D->>handlers: fetch variants, ASP, ISGL, ASPC
  D-->>U: Render variants page
```

## Edit assay config (ASPC)
```mermaid
sequenceDiagram
  participant A as Admin
  participant W as admin_bp
  participant H as ASPC Handler
  A->>W: GET /admin/aspc/<id>/edit
  W->>H: get_aspc(id)
  A->>W: POST (form)
  W->>H: update_aspc(...) + version bump
  W-->>A: Redirect with flash("Updated")
```

