import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  BookOpenCheck,
  CirclePlus,
  ListFilter,
  Plus,
  Trash2
} from "lucide-react";
import type {
  FactDefinition,
  OutputNode
} from "./clinical-rules-types";


export function OutputEditor({ nodes, facts, onChange }: { nodes: OutputNode[]; facts: FactDefinition[]; onChange: (nodes: OutputNode[]) => void }) {
  const replace = (index: number, node: OutputNode) => onChange(nodes.map((item, itemIndex) => itemIndex === index ? node : item))
  const scalarFacts = facts.filter((fact) => !["string_list", "object_list"].includes(fact.kind))
  const listFacts = facts.filter((fact) => fact.kind === "string_list")
  const numberFacts = facts.filter((fact) => ["integer", "number"].includes(fact.kind))
  return (
    <div className="space-y-2">
      {nodes.map((node, index) => (
        <div key={index} className="flex items-start gap-2 rounded-lg border border-border/70 bg-background/70 p-2">
          <div className="min-w-0 flex-1">
            {node.type === "text" && <textarea className="paper-inset min-h-24 w-full resize-y rounded-lg p-2 text-sm" value={node.value} onChange={(event) => replace(index, { ...node, value: event.target.value })} />}
            {node.type === "fact" && <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{scalarFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><select aria-label="Value format" className="paper-inset rounded-lg p-2 text-sm" value={node.formatter} onChange={(event) => replace(index, { ...node, formatter: event.target.value as typeof node.formatter })}><option value="text">As entered</option><option value="gene_symbol">Gene symbol</option><option value="upper">Uppercase</option><option value="lower">Lowercase</option></select><select aria-label="Missing value behavior" className="paper-inset rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require value</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "list" && <div className="grid gap-2 sm:grid-cols-[1fr_9rem_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{listFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><Input aria-label="List conjunction" value={node.conjunction} onChange={(event) => replace(index, { ...node, conjunction: event.target.value })} /><select aria-label="Missing list behavior" className="paper-inset rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require list</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "number" && <div className="grid gap-2 sm:grid-cols-[1fr_7rem_7rem_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{numberFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><label className="type-label">Decimals<Input className="mt-1" type="number" min={0} max={6} value={node.precision} onChange={(event) => replace(index, { ...node, precision: Number(event.target.value) })} /></label><label className="type-label">Unit<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={node.unit} onChange={(event) => replace(index, { ...node, unit: event.target.value as typeof node.unit })}><option value="">None</option><option value="%">%</option><option value="x">x</option></select></label><select aria-label="Missing number behavior" className="paper-inset self-end rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require number</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "message" && <div className="grid gap-2"><select className="paper-inset rounded-lg p-2 text-sm" value={node.count_path} onChange={(event) => replace(index, { ...node, count_path: event.target.value })}>{numberFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><Input aria-label="Text when count is one" placeholder="Text when count is one" value={node.one} onChange={(event) => replace(index, { ...node, one: event.target.value })} /><Input aria-label="Text for other counts" placeholder="Text for other counts" value={node.other} onChange={(event) => replace(index, { ...node, other: event.target.value })} /></div>}
            {node.type === "renderer" && <select className="paper-inset w-full rounded-lg p-2 text-sm" value={node.name} onChange={(event) => replace(index, { type: "renderer", name: event.target.value as typeof node.name })}><option value="dna_report_intro">DNA analysis introduction</option><option value="tier_summary">Tiered variant summary</option><option value="fusion_summary">Fusion summary</option></select>}
            {node.type === "paragraph_break" && <p className="py-2 text-xs font-medium text-muted-foreground">Paragraph break</p>}
          </div>
          <Button type="button" variant="ghost" size="icon-sm" title="Remove output part" disabled={nodes.length === 1} onClick={() => onChange(nodes.filter((_, itemIndex) => itemIndex !== index))}><Trash2 /></Button>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "text", value: "New report text" }])}><Plus /> Text</Button>
        <Button type="button" variant="outline" size="sm" disabled={!scalarFacts.length} onClick={() => onChange([...nodes, { type: "fact", path: scalarFacts[0]?.path || "finding.gene", formatter: "text", missing: "error" }])}><CirclePlus /> Value</Button>
        <Button type="button" variant="outline" size="sm" disabled={!listFacts.length} onClick={() => onChange([...nodes, { type: "list", path: listFacts[0]?.path || "finding.genes", conjunction: "and", formatter: "text", missing: "error" }])}><ListFilter /> List</Button>
        <Button type="button" variant="outline" size="sm" disabled={!numberFacts.length} onClick={() => onChange([...nodes, { type: "number", path: numberFacts[0]?.path || "aggregates.finding_count", precision: 0, unit: "", missing: "error" }])}><CirclePlus /> Number</Button>
        <Button type="button" variant="outline" size="sm" disabled={!numberFacts.length} onClick={() => onChange([...nodes, { type: "message", count_path: numberFacts[0]?.path || "aggregates.finding_count", one: "One finding", other: "Multiple findings" }])}><CirclePlus /> Singular / plural</Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "paragraph_break" }])}><BookOpenCheck /> Paragraph</Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "renderer", name: "tier_summary" }])}><ListFilter /> Structured summary</Button>
      </div>
    </div>
  )
}
