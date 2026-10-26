import { Button } from "@/components/ui/button"
import type { useDocumentEditor } from "@/hooks/useDocumentEditor"
import { LockKeyhole } from "lucide-react"

export function DocumentEditorNotice({ editor }: { editor: ReturnType<typeof useDocumentEditor> }) {
  if (!editor.enabled || editor.owned) return null
  return <section role="status" className="surface-panel flex items-start gap-3 p-3">
    <LockKeyhole className="size-4 shrink-0 text-muted-foreground" />
    <div className="space-y-2 type-body-sm">
      <p>{editor.pending ? "Opening editing session…" : editor.error || `${editor.owner || "Another user"} is editing this document. You can view it while they finish.`}</p>
      {!editor.pending && <><p className="text-muted-foreground">A separate tab or recently closed editor can hold this session, even under your own login. Leave that editor to release it. If disconnected, its lock expires within 90 seconds of the last renewal.</p><p className="text-muted-foreground">Keep a copy of any unsaved changes before reloading.</p><Button variant="outline" size="sm" onClick={() => window.location.reload()}>Reload document</Button></>}
    </div>
  </section>
}
