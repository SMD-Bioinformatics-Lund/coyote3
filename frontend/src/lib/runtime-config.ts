/**
 * Build-time runtime values supplied by Vite from deployment environment
 * variables. These are intentionally not read from individual pages.
 */
declare const __COYOTE3_RUNTIME__: {
  appVersion: string
  gensUri: string
  igvUri: string
  localTimeZone: string
  organizationName: string
  scriptName: string
}

export const runtimeConfig = __COYOTE3_RUNTIME__
