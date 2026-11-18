// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

type CopyNumberEvidence = { ratio?: unknown; log2?: unknown }

function measurement(value: unknown): number | null {
  if ((typeof value !== "number" && typeof value !== "string") || String(value).trim() === "") return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

/** Read an actual log2 measurement, preserving zero and missing evidence. */
export function cnvRatio(cnv: CopyNumberEvidence | null | undefined): number | null {
  return measurement(cnv?.ratio ?? cnv?.log2)
}

/** Derive a finite diploid copy estimate; overflow is unavailable evidence. */
export function cnvCopyNumber(cnv: CopyNumberEvidence | null | undefined): number | null {
  const ratio = cnvRatio(cnv)
  if (ratio === null) return null
  const estimate = 2 * Math.pow(2, ratio)
  return Number.isFinite(estimate) ? estimate : null
}

/** Apply the existing gain/loss purity adjustment only to usable measurements. */
export function purityAdjustedCopyNumber(cnv: CopyNumberEvidence, purity: unknown): number | null {
  const ratio = cnvRatio(cnv)
  const copyNumber = cnvCopyNumber(cnv)
  const purityValue = measurement(purity)
  if (ratio === null || copyNumber === null || purityValue === null || purityValue <= 0) return null
  const adjusted = ratio > 0 ? copyNumber / purityValue : copyNumber * purityValue
  return Number.isFinite(adjusted) ? adjusted : null
}
