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

Shared presentation lives in `src/components/ui/`. Use the following components
instead of copying page-specific border, background, badge or loading styles:

| Component | Use |
| --- | --- |
| `Surface` | Panel, raised card or inset background; the caller supplies padding and layout. |
| `SurfacePanel`, `Card`, `DetailCard` | Structured content with headings, actions or detail fields, built on `Surface`. |
| `Table` and its header, body, row and cell components | Static tables and the rendering layer of `DataTable`. |
| `DataTable` | Sorting, filtering, selection, exports and pagination. |
| `Badge`, `TableBadge`, `InfoBadge` | Shared badge geometry; semantic and domain colors retain their meaning. |
| `Notice` | Inline success, warning or error feedback; set a live-region role when needed. |
| `Button` | Action sizing, focus, hover and disabled states. |
| `GlobalRichTooltip`, `AppTooltip` | Shared pointer/keyboard hints and richer domain descriptions. |
| `LoadingIndicator`, `AppLoader` | Circular coyote emblem for inline progress or a labelled page loading state. |

`styles/tailwind-theme.css` owns theme tokens; `styles/page-materials.css` owns
surface treatment and `styles/tables.css` owns table density, borders and row
states. Use tokens in both themes. Keep compact INFO markers and circular tier
badges distinct because they convey specific finding information. Keep table
overflow inside its container, and preserve native table semantics and keyboard
access when composing controls. The loader respects reduced-motion preferences.
Packaged report paper retains its separate report presentation.

Tooltips show additional help, icon-only control names and clipped labels. Readable
button, link, badge and field labels do not generate duplicate hints; entered field
values are never copied into them. Give icon-only actions an `aria-label`.
Use `title`, `data-tooltip-content` or `aria-describedby` for additional help, and `AppTooltip` for
rich descriptions. Keep clinical badge content in its domain components, using
`TooltipSurface` and the shared positioning helpers. Pointer hints stay beside the
hovered target; keyboard hints stay attached to the focused control. Escape,
scrolling or leaving the window dismisses them. Disabled controls remain disabled
but can expose their explanation on hover. Use `data-tooltip-disabled="true"` to
opt out of shared hints or `data-native-title="true"` when a native title is required.

`AppFooter` sits outside each page's scroll viewport without `PageFrame` gutters.
In the application shell it spans the content column beside the full-height
sidebar; the page and navigation scroll independently. Authentication pages and
the error screen use the full window width. Each layout reserves the footer's
height so content remains reachable above it. Its compact raised surface uses
the shared paper/theme tokens; text wraps on narrow screens and respects the
device's bottom safe area.
