// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

/**
 * Build-time runtime values supplied by Vite from deployment environment
 * variables. These are intentionally not read from individual pages.
 */
declare const __COYOTE4_RUNTIME__: {
  appVersion: string
  environment: string
  gensUri: string
  igvUri: string
  igvDataRoot: string
  localTimeZone: string
  organizationName: string
  scriptName: string
}

export const runtimeConfig = __COYOTE4_RUNTIME__
