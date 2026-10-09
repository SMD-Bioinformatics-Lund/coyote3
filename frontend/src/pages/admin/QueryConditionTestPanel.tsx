import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { notifyActionError } from "@/lib/notifications"
import type { QueryCondition } from "./query-condition-types"
import { conditionNeedsSample } from "./query-condition-types"

export function QueryConditionTestPanel({ analysis, conditions }: {
  analysis: string; conditions: { id: string; condition: QueryCondition }[]
}) {
  const [selected, setSelected] = useState(0)
  const [examples, setExamples] = useState('[\n  {}\n]')
  const selectedIndex = Math.min(selected, Math.max(0, conditions.length - 1))
  const condition = conditions[selectedIndex]?.condition
  const fingerprint = JSON.stringify({ analysis, condition, examples })
  const test = useMutation({
    mutationFn: async () => {
      const documents: unknown = JSON.parse(examples)
      if (!Array.isArray(documents) || !documents.length || documents.length > 50 || documents.some(item => !item || Array.isArray(item) || typeof item !== "object")) throw new Error("Enter a JSON array containing 1–50 synthetic document objects.")
      if (!condition) throw new Error("Select an exception with a condition tree.")
      if (conditionNeedsSample(condition)) throw new Error("Use sample testing to resolve sample.filters references.")
      const response = await api.post<{ matches: boolean[]; predicate: unknown }>("/admin/query-rule-sets/test-condition", { analysis, condition, documents })
      return { ...response.data, fingerprint }
    },
    onError: error => notifyActionError("Unable to test condition", error, "Query rules"),
  })
  if (!conditions.length) return null
  return <details className="surface-panel rounded-lg border p-4 space-y-3">
    <summary className="cursor-pointer type-section-title">Test condition with synthetic examples</summary>
    <p className="text-muted-foreground">Tests the selected condition tree against the JSON documents below. No database records are read or saved. This does not evaluate base evidence, additional field criteria or sample access.</p>
    <label className="block type-label">Exception<select className="paper-inset w-full rounded-lg border p-2 text-sm" value={selectedIndex} onChange={event => setSelected(Number(event.target.value))}>{conditions.map((item, index) => <option key={index} value={index}>{item.id || `Exception ${index + 1}`}</option>)}</select></label>
    <label className="block type-label">Synthetic documents<textarea aria-label="Synthetic documents" className="paper-inset w-full rounded-lg border p-3 font-mono text-sm" rows={8} value={examples} onChange={event => setExamples(event.target.value)} /></label>
    {condition && conditionNeedsSample(condition) && <p className="type-supporting">This condition references sample.filters. Use Test with a sample.</p>}
    <Button type="button" variant="outline" disabled={test.isPending || !condition || conditionNeedsSample(condition)} onClick={() => test.mutate()}>Test condition</Button>
    {test.data?.fingerprint === fingerprint && !test.isPending && !test.isError && <div aria-live="polite" className="space-y-2">
      <ol className="space-y-1">{test.data.matches.map((matched, index) => <li key={index}>Example {index + 1}: <span className={matched ? "badge-success" : "badge-danger"}>{matched ? "Matches" : "Does not match"}</span></li>)}</ol>
      <details><summary className="cursor-pointer type-label">Compiled predicate</summary><pre className="overflow-auto rounded border bg-muted p-3 text-sm">{JSON.stringify(test.data.predicate, null, 2)}</pre></details>
    </div>}
  </details>
}
