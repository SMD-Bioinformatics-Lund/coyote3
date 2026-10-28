import { Dialog } from "@base-ui/react/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { offeringGeneMatches, type Offering } from "./offering-types"

/** Share exact gene-match counts and an accessible unmatched-gene dialog across views. */
export function CatalogGeneMatches({ offering, genes }: { offering: Offering; genes: readonly string[] }) {
  if (!genes.length) return null
  const { matched, unmatched } = offeringGeneMatches(offering, genes)
  return <div className="space-y-2 type-body-sm">
    <p className="font-semibold">{matched.length} / {genes.length} requested genes matched</p>
    {unmatched.length > 0 && <Dialog.Root>
      <Dialog.Trigger render={<Button variant="outline" size="sm" />}>View unmatched genes ({unmatched.length})</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-background/65 backdrop-blur-sm" />
        <Dialog.Popup className="glass-card fixed left-1/2 top-1/2 z-50 max-h-[85dvh] w-[min(36rem,95vw)] -translate-x-1/2 -translate-y-1/2 overflow-auto p-5">
          <Dialog.Title className="type-card-title">Unmatched genes - {offering.assay_display_name || offering.title}</Dialog.Title>
          <Dialog.Description className="my-3 type-body-sm text-muted-foreground">These genes are not in this test's published gene scope. This does not establish whether they are sequenced or clinically validated outside that scope.</Dialog.Description>
          <ul className="mb-4 flex flex-wrap gap-2" aria-label="Unmatched genes">{unmatched.map(gene => <li key={gene}><Badge variant="outline">{gene}</Badge></li>)}</ul>
          <Dialog.Close render={<Button variant="outline" />}>Close</Dialog.Close>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>}
  </div>
}
