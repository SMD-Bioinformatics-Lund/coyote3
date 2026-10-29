import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchInput } from "@/components/ui/search-input";
import { MarkdownComposer } from "@/components/comments/MarkdownComposer"
import { useState } from "react";
import { icon } from "@/lib/assets"
import type {
  FactDefinition,
  OutputNode
} from "./clinical-rules-types";


export function OutputEditor({ nodes, facts, onChange, readOnly = false }: { nodes: OutputNode[]; facts: FactDefinition[]; onChange: (nodes: OutputNode[]) => void; readOnly?: boolean }) {
  const [search, setSearch] = useState("")
  const insertFact = (fact: FactDefinition) => {
    const base = { path: fact.path, missing: "error" as const }
    const node: OutputNode = fact.kind === "string_list"
      ? { ...base, type: "list", formatter: "text", conjunction: "and" }
      : ["integer", "number"].includes(fact.kind)
        ? { ...base, type: "number", precision: fact.kind === "integer" ? 0 : 2, unit: "" }
        : { ...base, type: "fact", formatter: "text" }
    onChange([...nodes, node])
  }
  const replace = (index: number, node: OutputNode) => onChange(nodes.map((item, itemIndex) => itemIndex === index ? node : item))
  const scalarFacts = facts.filter((fact) => !["string_list", "object_list"].includes(fact.kind))
  const listFacts = facts.filter((fact) => fact.kind === "string_list")
  const numberFacts = facts.filter((fact) => ["integer", "number"].includes(fact.kind))
  return (
    <div className="space-y-2">
      <details className="rounded-lg border bg-background/70 p-3">
        <summary className="cursor-pointer font-medium">Insert dynamic value - assay, diagnosis, gene lists or findings</summary>
        <p className="my-2 text-sm text-muted-foreground">Choose a value to insert at the end, then move it between text parts. Gene counts come from selected lists, not the number of findings. Spaces and punctuation belong in your text parts.</p>
        <SearchInput aria-label="Search report values" placeholder="Search name, count, diagnosis, VAF…" value={search} onChange={event => setSearch(event.target.value)} />
        <div className="mt-2 max-h-64 space-y-3 overflow-auto">{[...new Set(facts.map(fact => fact.group))].map(group => {
          const matches = facts.filter(fact => fact.group === group && fact.kind !== "object_list" && `${fact.label} ${fact.path}`.toLowerCase().includes(search.toLowerCase()))
          return matches.length ? <section key={group}><h4 className="type-label mb-1">{group}</h4><div className="flex flex-wrap gap-1">{matches.map(fact => <Button key={fact.path} type="button" variant="outline" size="sm" title={fact.path} onClick={() => insertFact(fact)}><icon.plus />{fact.label}</Button>)}</div></section> : null
        })}</div>
      </details>
      {nodes.map((node, index) => (
        <div key={index} className="flex items-start gap-2 rounded-lg border border-border/70 bg-background/70 p-2">
          <div className="min-w-0 flex-1">
            {node.type === "text" && <MarkdownComposer label={`Text part ${index + 1}`} compact value={node.value} onChange={value => replace(index, { ...node, value })} maxLength={null} readOnly={readOnly} />}
            {node.type === "fact" && <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{scalarFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><select aria-label="Value format" className="paper-inset rounded-lg p-2 text-sm" value={node.formatter} onChange={(event) => replace(index, { ...node, formatter: event.target.value as typeof node.formatter })}><option value="text">As entered</option><option value="gene_symbol">Gene symbol</option><option value="upper">Uppercase</option><option value="lower">Lowercase</option></select><select aria-label="Missing value behavior" className="paper-inset rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require value</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "list" && <div className="grid gap-2 sm:grid-cols-[1fr_9rem_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{listFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><Input aria-label="List conjunction" value={node.conjunction} onChange={(event) => replace(index, { ...node, conjunction: event.target.value })} /><select aria-label="Missing list behavior" className="paper-inset rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require list</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "number" && <div className="grid gap-2 sm:grid-cols-[1fr_7rem_7rem_auto]"><select className="paper-inset rounded-lg p-2 text-sm" value={node.path} onChange={(event) => replace(index, { ...node, path: event.target.value })}>{numberFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><label className="type-label">Decimals<Input className="mt-1" type="number" min={0} max={6} value={node.precision} onChange={(event) => replace(index, { ...node, precision: Number(event.target.value) })} /></label><label className="type-label">Unit<select className="paper-inset mt-1 w-full rounded-lg p-2 text-sm" value={node.unit} onChange={(event) => replace(index, { ...node, unit: event.target.value as typeof node.unit })}><option value="">None</option><option value="%">%</option><option value="x">x</option></select></label><select aria-label="Missing number behavior" className="paper-inset self-end rounded-lg p-2 text-sm" value={node.missing} onChange={(event) => replace(index, { ...node, missing: event.target.value as typeof node.missing })}><option value="error">Require number</option><option value="omit">Omit if missing</option></select></div>}
            {node.type === "message" && <div className="grid gap-2"><select className="paper-inset rounded-lg p-2 text-sm" value={node.count_path} onChange={(event) => replace(index, { ...node, count_path: event.target.value })}>{numberFacts.map((fact) => <option key={fact.path} value={fact.path}>{fact.label}</option>)}</select><MarkdownComposer label="Text when count is one" compact value={node.one} onChange={one => replace(index, { ...node, one })} maxLength={null} readOnly={readOnly} /><MarkdownComposer label="Text for other counts" compact value={node.other} onChange={other => replace(index, { ...node, other })} maxLength={null} readOnly={readOnly} /></div>}
            {node.type === "renderer" && <select className="paper-inset w-full rounded-lg p-2 text-sm" value={node.name} onChange={(event) => replace(index, { type: "renderer", name: event.target.value as typeof node.name })}><option value="dna_report_intro">DNA analysis introduction</option><option value="tier_summary">Tiered variant summary</option><option value="fusion_summary">Fusion summary</option><option value="cnv_summary">Grouped CNV summary</option></select>}
            {node.type === "paragraph_break" && <p className="py-2 text-xs font-medium text-muted-foreground">Paragraph break</p>}
          </div>
          <div className="flex flex-col gap-1"><Button type="button" variant="ghost" size="sm" aria-label={`Move output part ${index + 1} up`} disabled={index === 0} onClick={() => { const next = [...nodes]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; onChange(next) }}>↑</Button><Button type="button" variant="ghost" size="sm" aria-label={`Move output part ${index + 1} down`} disabled={index === nodes.length - 1} onClick={() => { const next = [...nodes]; [next[index + 1], next[index]] = [next[index], next[index + 1]]; onChange(next) }}>↓</Button><Button type="button" variant="ghost" size="icon-sm" title="Remove output part" disabled={nodes.length === 1} onClick={() => onChange(nodes.filter((_, itemIndex) => itemIndex !== index))}><icon.trash2 /></Button></div>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "text", value: "New report text" }])}><icon.plus /> Text</Button>
        <Button type="button" variant="outline" size="sm" disabled={!scalarFacts.length} onClick={() => onChange([...nodes, { type: "fact", path: scalarFacts[0]?.path || "finding.gene", formatter: "text", missing: "error" }])}><icon.circlePlus /> Value</Button>
        <Button type="button" variant="outline" size="sm" disabled={!listFacts.length} onClick={() => onChange([...nodes, { type: "list", path: listFacts[0]?.path || "finding.genes", conjunction: "and", formatter: "text", missing: "error" }])}><icon.listFilter /> List</Button>
        <Button type="button" variant="outline" size="sm" disabled={!numberFacts.length} onClick={() => onChange([...nodes, { type: "number", path: numberFacts[0]?.path || "aggregates.finding_count", precision: 0, unit: "", missing: "error" }])}><icon.circlePlus /> Number</Button>
        <Button type="button" variant="outline" size="sm" disabled={!numberFacts.length} onClick={() => onChange([...nodes, { type: "message", count_path: numberFacts[0]?.path || "aggregates.finding_count", one: "One finding", other: "Multiple findings" }])}><icon.circlePlus /> Singular / plural</Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "paragraph_break" }])}><icon.bookOpenCheck /> Paragraph</Button>
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...nodes, { type: "renderer", name: "tier_summary" }])}><icon.listFilter /> Structured summary</Button>
      </div>
    </div>
  )
}
