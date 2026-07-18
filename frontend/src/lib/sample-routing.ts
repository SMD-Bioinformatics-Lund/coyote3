export function sampleUrlKey(sample: any, fallback?: unknown) {
  const key = sample?.name || sample?.sample_name || fallback || sample?._id || sample?.id
  return encodeURIComponent(String(key || ""))
}

export function sampleDetailPath(sample: any, fallback?: unknown) {
  return `/samples/${sampleUrlKey(sample, fallback)}`
}

export function sampleFindingPath(
  sample: any,
  fallback: unknown,
  findingType: "variant" | "cnv" | "fusion" | "translocation",
  findingId: unknown,
) {
  return `${sampleDetailPath(sample, fallback)}/${findingType}/${encodeURIComponent(String(findingId || ""))}`
}
