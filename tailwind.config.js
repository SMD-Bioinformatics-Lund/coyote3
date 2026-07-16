/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./frontend/index.html",
    "./frontend/src/**/*.{ts,tsx,js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "var(--card)",
          muted: "var(--muted)",
          accent: "var(--accent)",
        },
        clinical: {
          dna: "var(--color-dna)",
          rna: "var(--color-rna)",
          panel: "var(--color-panel)",
          pass: "var(--color-pass)",
          warn: "var(--color-warn)",
          fail: "var(--color-fail)",
          unknown: "var(--color-unknown)",
        },
        tier: {
          1: "var(--color-tier1)",
          2: "var(--color-tier2)",
          3: "var(--color-tier3)",
          4: "var(--color-tier4)",
          other: "var(--color-tierother)",
        },
      },
      boxShadow: {
        panel: "0 10px 28px color-mix(in srgb, var(--foreground) 8%, transparent)",
        control: "0 2px 8px color-mix(in srgb, var(--foreground) 8%, transparent)",
      },
    },
  },
  safelist: [
    // Dynamic semantic classes assembled from API metadata.
    {
      pattern:
        /(bg|text|border|ring|from|to|via)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|brown|olive|sage|sand|mist)-([0-9]{2,3})/,
      variants: ["hover", "focus"],
    },
    // Dynamic non-shaded palette classes from data-driven UI values.
    {
      pattern:
        /(bg|text|border|ring|from|to|via)-(black|white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|brown|olive|sage|sand|mist)/,
      variants: ["hover", "focus"],
    },
    // Dynamic semantic classes for tiers, profiles, QC/hotspot badges, and assay scopes.
    {
      pattern:
        /(bg|text|border|ring|from|to|via)-(production|validation|development|testing|pass|warn|fail|germline|germline-risk|tier1|tier2|tier3|tier4|tier999|tierother|tier-header1|tier-header2|tier-header3|tier-header4|tier-header999|melanoma|cns|lung|colon|gi|dna|rna|genelist|fusionlist|cnvlist|panel|wts|wgs|unknown)/,
      variants: ["hover", "focus"],
    },
  ],
  plugins: [],
};
