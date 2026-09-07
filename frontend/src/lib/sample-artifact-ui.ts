export type SampleFileAvailability =
  | "available"
  | "unreadable"
  | "required_missing"
  | "optional_missing"

type ArtifactPresentation = {
  label: string
  missingMessage: string
  countSuffix?: string
  countIsStatus?: boolean
}

const ARTIFACT_PRESENTATION: Record<string, ArtifactPresentation> = {
  SNV: { label: "VCF", missingMessage: "No VCF file available", countSuffix: "SNVs" },
  CNV: { label: "CNV JSON", missingMessage: "No CNV JSON available", countSuffix: "CNVs" },
  TRANSLOCATION: { label: "Transloc VCF", missingMessage: "No Transloc VCF available", countSuffix: "Translocs" },
  COVERAGE: { label: "Coverage JSON", missingMessage: "No coverage file available", countSuffix: "Loaded", countIsStatus: true },
  BIOMARKER: { label: "Biomarkers JSON", missingMessage: "No biomarkers file available", countSuffix: "Loaded", countIsStatus: true },
  CNV_PROFILE: { label: "CNV Profile (image)", missingMessage: "No CNV profile available" },
  FUSION: { label: "Fusion calls", missingMessage: "No fusion file available", countSuffix: "Fusions" },
  EXPRESSION: { label: "Expression", missingMessage: "No expression file available", countSuffix: "Expr" },
  CLASSIFICATION: { label: "Classification", missingMessage: "No classification file available", countSuffix: "classes" },
  QC: { label: "QC", missingMessage: "No QC file available", countSuffix: "data" },
}

const DEFAULT_PRESENTATION: ArtifactPresentation = {
  label: "Analysis file",
  missingMessage: "No file available",
}

export function sampleArtifactPresentation(analysisType: unknown): ArtifactPresentation {
  return ARTIFACT_PRESENTATION[String(analysisType || "").trim().toUpperCase()] || DEFAULT_PRESENTATION
}

export function sampleArtifactCountLabel(analysisType: unknown, count: unknown): string | null {
  const numericCount = Number(count)
  if (!Number.isFinite(numericCount) || numericCount <= 0) return null
  const presentation = sampleArtifactPresentation(analysisType)
  if (!presentation.countSuffix) return null
  return presentation.countIsStatus
    ? presentation.countSuffix
    : `${numericCount.toLocaleString()} ${presentation.countSuffix}`
}

export function sampleArtifactStatus(availability: unknown): { label: string; tone: "green" | "red" | "yellow" } {
  switch (availability as SampleFileAvailability) {
    case "available":
      return { label: "Uploaded", tone: "green" }
    case "unreadable":
      return { label: "Broken path", tone: "red" }
    case "required_missing":
      return { label: "Required missing", tone: "red" }
    default:
      return { label: "Optional missing", tone: "yellow" }
  }
}
