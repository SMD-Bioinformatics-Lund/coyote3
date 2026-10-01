import { ClipboardCheck, Dna, FileCheck, Layers, ListTree, Settings2 } from "lucide-react"
import { cn } from "@/lib/utils"

const steps = [
  { name: "Assay", icon: Dna },
  { name: "Scopes", icon: Layers },
  { name: "Gene lists", icon: ListTree },
  { name: "Reporting rules", icon: FileCheck },
  { name: "Configurations", icon: Settings2 },
  { name: "Review", icon: ClipboardCheck },
]

export function SetupNavigation({ step, isNew, pending, onChange }: {
  step: number
  isNew: boolean
  pending: boolean
  onChange: (step: number) => void
}) {
  return (
    <nav aria-label="Assay setup steps" className="surface-panel min-w-0 p-2">
      <ol className="grid min-w-0 grid-cols-2 gap-1 md:grid-cols-3 xl:grid-cols-6">
        {steps.map(({ name, icon: Icon }, index) => (
          <li key={name} className="min-w-0">
            <button
              type="button"
              aria-current={step === index ? "step" : undefined}
              disabled={pending || (isNew && index !== 0)}
              onClick={() => onChange(index)}
              className={cn(
                "flex h-full min-h-16 w-full min-w-0 items-center gap-2 rounded-lg border p-3 text-left type-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
                step === index
                  ? "border-primary/30 bg-primary/10 text-primary"
                  : "border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground",
              )}
            >
              <Icon aria-hidden="true" className="size-4 shrink-0" />
              <span className="min-w-0 break-words">{index + 1}. {name}</span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}
