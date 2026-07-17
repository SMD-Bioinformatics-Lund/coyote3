export function isFlaggedFinding(finding: any) {
  return Boolean(
    finding?.fp ||
      finding?.blacklisted ||
      (finding?.blacklist && finding?.override_blacklist !== true),
  )
}

export function findingRowClass(finding: any) {
  return isFlaggedFinding(finding)
    ? "!bg-fail/5 text-foreground/85 hover:!bg-fail/10 dark:!bg-fail/10 dark:hover:!bg-fail/15"
    : "hover:bg-primary/10 dark:hover:bg-primary/20"
}

export function tierValue(finding: any) {
  const raw = finding?.classification?.class ?? finding?.classification?.tier ?? finding?.tier
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : 999
}

export function statusLabels(finding: any) {
  const labels: string[] = []
  if (finding?.fp) labels.push("False positive")
  if (finding?.blacklisted || (finding?.blacklist && finding?.override_blacklist !== true)) labels.push("Blacklisted")
  if (finding?.irrelevant) labels.push("Irrelevant")
  if (finding?.interesting) labels.push("Interesting")
  if (Array.isArray(finding?.comments) && finding.comments.length > 0) labels.push("Has comments")
  return labels.join(" | ")
}

export function filterFlags(value: unknown) {
  const raw = Array.isArray(value) ? value : [value]
  return raw
    .flatMap((item) => String(item ?? "").split(","))
    .map((item) => item.trim())
    .filter(Boolean)
}

export function normalizedCallerList(value: unknown) {
  const raw = Array.isArray(value) ? value : String(value || "").split(/[,&]/)
  return raw.map((item) => String(item || "").trim()).filter((item) => Boolean(item) && item !== "-")
}

export function selectedFusionCall(fusion: any) {
  if (Array.isArray(fusion?.calls) && fusion.calls.length > 0) {
    return fusion.calls.find((call: any) => call?.selected === 1 || call?.selected === true) ?? fusion.calls[0]
  }

  return {
    effect: fusion?.frame,
    spanpairs: fusion?.supporting_reads?.span,
    spanreads: fusion?.supporting_reads?.split,
    breakpoint1: fusion?.breakpoints?.[0],
    breakpoint2: fusion?.breakpoints?.[1],
    desc: fusion?.desc,
    caller: Array.isArray(fusion?.callers) ? fusion.callers.join(", ") : fusion?.callers,
  }
}

export function fusionGenes(fusion: any) {
  if (typeof fusion?.genes === "string") return fusion.genes.split("^")
  if (Array.isArray(fusion?.genes)) return fusion.genes
  if (typeof fusion?.fusion_name === "string") return fusion.fusion_name.split("--")
  return []
}

export function fusionCallers(fusion: any) {
  if (Array.isArray(fusion?.calls)) {
    return Array.from(new Set(fusion.calls.map((call: any) => call?.caller).filter(Boolean))).join(", ")
  }
  return Array.isArray(fusion?.callers) ? fusion.callers.join(", ") : (fusion?.callers ?? "-")
}

export function selectedTranslocationAnnotation(translocation: any) {
  const mane = translocation?.INFO?.MANE_ANN ?? translocation?.MANE_ANN
  if (Array.isArray(mane)) return mane[0] ?? {}
  if (mane && typeof mane === "object") return mane
  const annotations = translocation?.INFO?.ANN ?? translocation?.ANN
  if (Array.isArray(annotations)) return annotations[0] ?? {}
  if (annotations && typeof annotations === "object") return annotations
  return {}
}

export function translocationGenes(translocation: any) {
  if (Array.isArray(translocation?.genes) && translocation.genes.length > 0) {
    return translocation.genes.map((gene: unknown) => String(gene || "").trim()).filter(Boolean)
  }
  if (typeof translocation?.genes === "string" && translocation.genes.trim()) {
    return translocation.genes.split(/[&^,;/]+/).map((gene: string) => gene.trim()).filter(Boolean)
  }
  const annotation = selectedTranslocationAnnotation(translocation)
  const geneText =
    annotation?.Gene_Name ??
    annotation?.Gene ??
    annotation?.SYMBOL ??
    annotation?.gene ??
    translocation?.INFO?.Gene_Name ??
    translocation?.INFO?.GENE ??
    translocation?.gene
  if (typeof geneText === "string" && geneText.trim()) {
    return geneText.split(/[&^,;/]+/).map((gene: string) => gene.trim()).filter(Boolean)
  }
  return [translocation?.gene1, translocation?.gene2]
    .map((gene) => String(gene || "").trim())
    .filter(Boolean)
}

export function translocationHgvs(annotation: any) {
  return {
    coding: annotation?.HGVSc ?? annotation?.HGVS_c ?? annotation?.hgvsc ?? annotation?.hgvs_c,
    protein: annotation?.HGVSp ?? annotation?.HGVS_p ?? annotation?.hgvsp ?? annotation?.hgvs_p,
  }
}

export function translocationType(translocation: any) {
  const raw = translocation?.INFO?.SVTYPE ?? translocation?.SVTYPE ?? translocation?.svtype ?? translocation?.type
  const annotation = selectedTranslocationAnnotation(translocation)
  const terms = annotation?.Annotation ?? annotation?.Consequence
  if (Array.isArray(terms) && terms.length > 0) return terms.join(", ")
  if (raw) return String(raw)
  return "BND"
}

export function translocationPanelStatus(translocation: any) {
  const raw = translocation?.INFO?.PANEL ?? translocation?.INFO?.panel ?? translocation?.panel
  if (raw === true) return "Yes"
  if (raw === false) return "No"
  const text = String(raw ?? "").trim()
  if (!text || text === "-") return "-"
  if (text.toUpperCase() === "IN") return "Yes"
  if (text.toUpperCase() === "OUT") return "No"
  return text
}

export function translocationPositionLabel(translocation: any) {
  const chrom = translocation?.CHROM ?? translocation?.chrom ?? translocation?.INFO?.CHROM
  const pos = translocation?.POS ?? translocation?.pos
  const left = chrom && pos ? `${chrom}:${pos}` : String(pos || "-")
  const alt = translocationAlt(translocation)
  if (alt) return `${left} ${alt}`
  const chrom2 = translocation?.INFO?.CHR2 ?? translocation?.chrom2
  const end = translocation?.INFO?.END ?? translocation?.end
  if (chrom2 || end) return `${left} ${chrom2 || "-"}:${end || "-"}`
  return left
}

export function translocationAlt(translocation: any) {
  const alt = translocation?.ALT ?? translocation?.INFO?.ALT
  return Array.isArray(alt) ? alt[0] : alt
}
