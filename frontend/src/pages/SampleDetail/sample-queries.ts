// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import type { QueryClient } from "@tanstack/react-query"

export function invalidateSampleQueries(queryClient: QueryClient, sampleId: string) {
  for (const key of [
    "sample",
    "sample-variants",
    "sample-cnvs",
    "sample-fusions",
    "sample-translocations",
    "sample-coverage",
    "sample-genelists",
    "sample-effective-genes",
    "sample-comment-suggestion",
    "report-preview",
  ]) {
    queryClient.invalidateQueries({ queryKey: [key, sampleId] })
  }
  queryClient.invalidateQueries({ queryKey: ["samples"] })
}
