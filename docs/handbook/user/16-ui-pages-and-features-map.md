# UI Pages and Features Map

This chapter describes the UI surface only: what users can do on each page.

Backend implementation details are intentionally excluded.

## Authentication

- **Login page**
  - Sign in with username/password.
  - Redirect to dashboard on success.
- **Logout**
  - Ends active session and returns to login screen.

## Dashboard

- Case and sample overview widgets.
- Quick navigation to workflow pages.
- Summary-level operational visibility.

## DNA pages

- **Variant list**
  - Filter and inspect variants.
  - Access annotation/classification actions.
- **Variant detail**
  - Inspect evidence, comments, and classifications.
- **CNV and translocation pages**
  - View and review non-SNV findings.
- **DNA reporting**
  - Preview report output and trigger save actions.

## RNA pages

- **Fusion list**
  - Filter fusion calls and review candidates.
- **Fusion detail**
  - Inspect selected call, comments, and classification context.
- **RNA reporting**
  - Preview report output and trigger save actions.

## Common/shared pages

- Sample comments and history views.
- Tiered/interesting finding summaries.
- Shared table/filter utilities.

## Admin pages

- User management.
- Role and permission management.
- Assay panel / config / schema management.
- Gene list management.
- Audit views and governance controls.

## Public pages

- Catalog search/discovery pages.
- Gene list and metadata lookup pages.

## User profile pages

- Current user profile and account-related UI settings.

## UI design constraints

- UI pages should remain focused on user workflows and rendering.
- Access control and data-validation outcomes are shown in UI, but enforcement happens in backend APIs.
- New UI features should be documented in this map and in the relevant workflow chapter.
