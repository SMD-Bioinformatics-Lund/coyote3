# Frontend architecture

React pages coordinate clinical and administrative interactions. Shared components
provide forms, tables, dialogs and layout. Route and query abstractions centralize
HTTP access; generated contracts describe the API's wire types.

The frontend owns navigation, loading/error states, selection, editing interactions
and presentation. It does not evaluate authoritative clinical rules or grant
permissions. Hidden buttons and client-side validation do not replace server checks.

Report paper is rendered through the API using `smd-reports`. Surrounding browser
controls manage preview, download and finalization actions; UI code must not
rewrite clinical text or substitute its own report template.

Reuse the shared theme tokens, layout primitives and existing accessible controls.
Preserve light/dark presentation, keyboard access and narrow-screen behavior when
changing a component.
