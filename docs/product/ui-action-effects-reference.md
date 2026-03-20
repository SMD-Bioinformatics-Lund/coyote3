# UI Action Effects Reference

This page maps common UI button labels to:

1. what action is executed,
2. what data/state is changed,
3. what the user sees immediately after.

It is intended for users, QA, and developers.

## Scope notes

- This reference covers actions that change state, not read-only navigation links.
- Some controls are display-only toggles in browser state (no backend mutation).
- Permission checks still apply; unavailable buttons may be hidden or disabled by role.

## Sample and home actions

| UI label | Where | Backend action | State change | Visible result |
|---|---|---|---|---|
| `Apply selected` | Sample settings (`Choose Gene Lists`) | `POST /home/<sample_id>/apply_isgl` | Updates `samples.filters.genelists` | Effective gene scope and variant summary counts refresh |
| `Paste Ad-Hoc Genes` -> `Save` | Sample settings modal | `POST /home/<sample_id>/adhoc_genes` | Updates `samples.filters.adhoc_genes` | Ad-hoc chips/list and effective genes update |
| `Clear Ad-Hoc Genes` | Sample settings | `POST /home/<sample_id>/adhoc_genes/clear` | Removes `samples.filters.adhoc_genes` | Ad-hoc block clears; effective scope returns to baseline |
| `View all` (Effective genes) | Sample settings | `GET /home/<sample_id>/effective-genes/all` | No persisted mutation | Full effective gene list modal opens |
| `View all comments` | Sample settings | Client modal only | No persisted mutation | Full comment modal opens |
| `Download` (report row) | Sample settings report card | report file stream endpoint | No persisted mutation | Report file download starts |

## DNA list and filter actions

| UI label | Where | Backend action | State change | Visible result |
|---|---|---|---|---|
| `Apply` (DNA filters) | DNA sidebar | `PUT /samples/{id}/filters` | Updates `samples.filters` (DNA keys) | Variant/CNV/translocation lists recalculate |
| `Reset` (DNA filters) | DNA sidebar | `DELETE /samples/{id}/filters` | Restores default assay filter profile | Lists reload with default thresholds |
| `Apply` (bulk panel) | DNA sidebar bulk actions | patch bulk endpoints for tier/flags | Bulk updates selected variant flags/tier | Rows show updated tags and chips |
| `Remove` (bulk panel) | DNA sidebar bulk actions | patch bulk endpoints with `apply=false` | Removes selected flags/tier assignments | Rows lose corresponding tags/chips |
| `Hide FPs` | DNA sidebar | Client toggle | No persisted mutation | False-positive rows are hidden/shown locally |
| `Preview Report` | DNA findings | report preview endpoint | No persisted mutation | Report preview page opens |
| `Finalize Report` | DNA report preview | save report endpoint | Adds report metadata + snapshot rows (`reported_variants`) | Success flash and report availability in history |

## DNA detail actions (SNV/CNV/Translocation)

| UI label | Where | Backend action | State change | Visible result |
|---|---|---|---|---|
| `Mark as False Positive` | SNV/CNV/translocation detail | `PATCH .../flags/false-positive` | Sets false-positive flag | Badge/state changes; row can be hidden by FP filter |
| `Unmark False Positive` | SNV/CNV/translocation detail | `DELETE .../flags/false-positive` | Clears false-positive flag | FP badge removed |
| `Mark as Interesting` | SNV detail | `PATCH .../flags/interesting` | Sets interesting flag | Interesting marker appears |
| `Unmark Interesting` | SNV detail | `DELETE .../flags/interesting` | Clears interesting flag | Interesting marker removed |
| `Mark as Irrelevant` | SNV detail | `PATCH .../flags/irrelevant` | Sets irrelevant flag | Irrelevant marker appears/de-prioritized |
| `Unmark Irrelevant` | SNV detail | `DELETE .../flags/irrelevant` | Clears irrelevant flag | Irrelevant marker removed |
| `Mark Noteworthy` | CNV detail | `PATCH .../flags/noteworthy` | Sets noteworthy flag | Noteworthy indicator appears |
| `Unmark Noteworthy` | CNV detail | `DELETE .../flags/noteworthy` | Clears noteworthy flag | Noteworthy indicator removed |
| `Classify` (tier buttons) | SNV/fusion classification card | `POST /dna_sample/{id}/classifications` | Creates/updates classification context for target | Tier/classification chips update |
| `Remove ... classifications` | SNV/fusion classification card | `DELETE /dna_sample/{id}/classifications` | Removes selected classification scope | Historical/current tier chips removed |
| `Save` (comment) | SNV/CNV/translocation/fusion detail comment form | `POST /dna_sample/{id}/annotations` | Adds annotation/comment record (optionally global scope) | Comment list gains new entry |
| `Show/Hide Deleted Comments` + hide/unhide buttons | Detail pages | patch/delete hidden-comment endpoint | Toggles hidden status on comments | Deleted/hidden comments appear or collapse |
| `Add to blacklist` (variant context) | SNV detail | `POST .../blacklist-entries` | Adds blacklist entry | Variant flagged as blacklisted in views/metrics |

## RNA list and detail actions

| UI label | Where | Backend action | State change | Visible result |
|---|---|---|---|---|
| `Apply` (RNA filters) | RNA sidebar | `PUT /samples/{id}/filters` | Updates `samples.filters` (RNA keys) | Fusion list recalculates |
| `Reset` (RNA filters) | RNA sidebar | `DELETE /samples/{id}/filters` | Restores default fusion filters | Fusion list reloads with defaults |
| `Apply` / `Remove` (bulk) | RNA sidebar bulk actions | `PATCH .../fusions/flags/{flag}` with fusion ids | Bulk apply/remove `false-positive` or `irrelevant` | Selected rows update flag status |
| `Mark as False Positive` | Fusion detail | `PATCH .../fusions/{id}/flags/false-positive` | Sets fusion false-positive flag | Flag marker appears |
| `Unmark False Positive` | Fusion detail | `DELETE .../fusions/{id}/flags/false-positive` | Clears fusion false-positive flag | Flag marker removed |
| `Pick call` (call selection link/button) | Fusion detail calls table | `PATCH .../selection/{callidx}/{num_calls}` | Changes selected fusion call | Active call row/details update |
| `Classify Fusion` | Fusion detail | classification endpoint (shared class flow) | Adds classification context for fusion | Tier/class chips update |
| `Remove classifications` | Fusion detail | classification delete endpoint | Removes selected fusion classifications | Tier/class chips removed |
| `Save` (fusion comment) | Fusion detail | annotation endpoint | Adds fusion annotation/comment | Comment appears in list |
| `Finalize Report` | RNA report preview | save report endpoint | Persists report metadata/snapshot | Report available in sample history |

## Common sample comment actions

| UI label | Where | Backend action | State change | Visible result |
|---|---|---|---|---|
| `Add sample comment` / `Save` | DNA/RNA sample-level comment forms | `POST /samples/{id}/comments` | Appends sample comment | New comment appears in sample comments |
| `Hide sample comment` | Sample comment actions | `PATCH /samples/{id}/comments/{comment_id}/hidden` | Marks sample comment hidden | Hidden from default list |
| `Unhide sample comment` | Sample comment actions | `DELETE /samples/{id}/comments/{comment_id}/hidden` | Restores comment visibility | Comment reappears |

## Auth and user profile actions

| UI label | Where | Backend action | State change | Visible result |
|---|---|---|---|---|
| `Send Reset Link` | Forgot password page | password reset request endpoint | Issues reset token (if eligible) | Success message (non-enumerating) |
| `Reset Password` submit | Reset password page | password reset confirm endpoint | Updates local user password | Redirect to login with success/failure |
| `Change Password` submit | Profile password page | password change endpoint | Changes current user password | Success flash; credentials updated |
| `Logout` | Header/menu | logout endpoint + session clear | Invalidates session and API cookie | Redirect to login |

## Admin actions

| UI label | Where | Backend action | State change | Visible result |
|---|---|---|---|---|
| `Save User` | Admin user create/edit | `POST/PUT /admin/users...` | Creates or updates user doc | User list reflects change |
| `Toggle` user active | Admin users list | `PATCH /admin/users/{id}/status` | Flips `is_active` | Status chip updates |
| `Delete` user | Admin users list | `DELETE /admin/users/{id}` | Removes user doc | User removed from list |
| `Send Invite` | Admin users list | `POST /admin/users/{id}/invite` | Generates invite token; attempts email | Success/warning flash; manual URL fallback if mail unavailable |
| `Save Role` / `Save Permission` | Admin roles/permissions | `POST/PUT` role/permission endpoints | Creates/updates policy docs | Lists and detail pages update |
| `Toggle` role/permission/schema | Admin pages | patch status endpoints | Flips `is_active` | Active status updates |
| `Delete` role/permission/schema | Admin pages | delete endpoints | Removes selected document | Removed from listing |
| `Save Panel` (`ASP`) | Admin assay panel page | create/update ASP endpoints | Updates assay panel doc | Panel catalog and config context update |
| `Save Assay Config` (`ASPC`) | Admin assay config page | create/update ASPC endpoints | Updates assay+environment config doc | Runtime filter/report config updates |
| `Save ISGL` | Admin genelists page | create/update ISGL endpoints | Updates curated gene list docs | ISGL options and gene coverage context update |
| `Delete Sample` (admin) | Admin samples | sample delete endpoint | Removes sample and dependent resources | Sample disappears from admin and user views |

## Local (no backend mutation) controls

These controls change display only:

1. `Hide FPs` view toggle.
2. Sidebar collapse/expand toggles.
3. Table pagination controls in client-paginated tables.
4. `Show more/Show less` text expansion controls.
5. Dashboard chart mode toggles (ASP genes vs ISGL count view).

## QA checklist shortcut

For each action test:

1. Trigger action in UI.
2. Confirm flash/success response.
3. Refresh page and verify state persisted (except local controls).
4. Confirm related summaries/lists reflect the changed state.
