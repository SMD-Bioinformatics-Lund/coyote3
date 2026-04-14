# UI Action Modal

Use the shared layout action modal for any UI action that needs user
confirmation. This keeps destructive flows consistent across Flask pages and
avoids mixing browser `confirm()` calls, page-local dialog markup, and
inconsistent warning styles.

## When to use it

Use the action modal when a page is about to:

- submit a destructive form
- navigate to a state-changing route
- run a client-side callback after explicit confirmation

Do not create page-local modal markup for these cases.

## Supported patterns

### 1. Confirm a URL navigation

This is the simplest pattern and is still used by the admin list pages.

```html
<button
  type="button"
  onclick="showActionModal({
    url: '{{ url_for('admin_bp.edit_user', user_id=user._id) }}',
    title: 'Edit user',
    message: 'Open the edit screen for <b>{{ user.username }}</b>?',
    confirmText: 'Edit',
    confirmColor: 'blue'
  })"
>
  Edit
</button>
```

When the user confirms, the helper navigates with `window.location.assign(...)`.

### 2. Confirm a form submission

Preferred for destructive POST actions such as removing a tier or overriding a
blacklist flag.

```html
<form
  action="{{ url_for('dna_bp.override_variant_blacklist', sample_id=sample_id, var_id=variant._id) }}"
  method="post"
  data-action-modal-form
  data-action-modal-title="Override Blacklist"
  data-action-modal-message="This will keep the variant visible for this sample."
  data-action-modal-confirm-text="Override blacklist"
  data-action-modal-confirm-color="purple"
>
  <input type="submit" value="Override Blacklist">
</form>
```

The shared JS intercepts the form submission, opens the modal, and on confirm
calls `form.requestSubmit()`.

### 3. Confirm a client-side callback

Use this for async page actions that do not map directly to a single form or
navigation target.

```javascript
showActionModal({
  title: "Clear Ad-Hoc Genes",
  message: "This will remove the saved ad-hoc gene list from this sample.",
  confirmText: "Clear genes",
  confirmColor: "yellow",
  onConfirm: async () => {
    const response = await fetch(clearUrl, { method: "POST" });
    if (response.ok) {
      window.location.reload();
    }
  },
});
```

## API surface

`showActionModal(...)` supports:

- `url`
- `form`
- `title`
- `message`
- `confirmText`
- `confirmColor`
- `onConfirm`

Color variants currently supported:

- `blue`
- `green`
- `yellow`
- `orange`
- `purple`
- `red`
- `gray`

## Behavior notes

- clicking the backdrop closes the modal
- pressing `Escape` closes the modal
- the close button and cancel button both dismiss the modal
- use HTML in `message` only when the content is trusted template output

## Rule of thumb

If a route action already lives in a `<form method="post">`, prefer
`data-action-modal-form` over inline JavaScript. Reserve direct
`showActionModal({ onConfirm })` calls for client-side actions that genuinely do
not map to a form.
