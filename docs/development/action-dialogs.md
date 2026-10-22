# React action confirmations

Use `ConfirmationDialog` from `@/components/ui/confirmation-dialog` for reviewed
state-changing actions. It renders an accessible portal, traps keyboard focus,
restores focus on close and prevents cancellation while the action is pending.
See [actions and record changes](../user-guide/actions-and-record-changes.md) for
user-facing behavior.

## Component contract

| Prop | Purpose |
| --- | --- |
| `open`, `title`, `description` | Controlled visibility and the action/resource/consequence to confirm. Description accepts React content. |
| `confirmLabel`, `cancelLabel` | Action labels; defaults are Confirm and Cancel. |
| `isPending` | Disable both actions and cancellation while the request is running. |
| `confirmDisabled` | Disable confirmation until the form meets its prerequisites. |
| `variant` | `default` or `destructive`; presentation does not grant permission. |
| `onConfirm`, `onCancel` | Callbacks owned by the page or reusable workflow. |

The component does not call the API, manage mutation errors or automatically close
after confirmation. The owner uses the existing API/query abstraction, reports the
result through the notification helpers, and refreshes affected cached data.

## Example

This synthetic component receives an existing mutation callback; it does not invent
an API endpoint:

```tsx
import { useState } from "react"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"

type Props = {
  sampleName: string
  isPending: boolean
  deleteSample: () => Promise<boolean>
}

export function DeleteSampleConfirmation({ sampleName, isPending, deleteSample }: Props) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Delete sample</button>
      <ConfirmationDialog
        open={open}
        title={`Delete ${sampleName}?`}
        description="Remove the sample's owned records and queue its generated report files for erasure."
        variant="destructive"
        confirmLabel="Delete sample"
        isPending={isPending}
        onCancel={() => setOpen(false)}
        onConfirm={async () => {
          if (await deleteSample()) setOpen(false)
        }}
      />
    </>
  )
}
```

The supplied callback reports failed requests through the existing notification
helpers and returns false, retaining the dialog without an unhandled rejection.
A confirmation does not replace server authorization, sample/finding ownership or
transaction checks. Sample deletion still requires `sample:delete:global`.

For ordinary reversible edits, use the existing form workflow unless an explicit
confirmation is required. Do not add a second dialog implementation or a browser
`confirm()` around the shared dialog. Pending, cancellation, keyboard and focus
behavior are covered by its component tests.
