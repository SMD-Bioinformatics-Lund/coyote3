const colors = require("tailwindcss/colors");

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./coyote/templates/**/*.html",
    "./coyote/blueprints/**/templates/**/*.html",
    "./coyote/static/js/**/*.js",
    "./coyote/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        // Legacy project palettes used throughout templates.
        brown: {
          50: "#f5f5ef",
          100: "#e2d6c0",
          200: "#caae80",
          300: "#b08d57",
          400: "#926a3d",
          500: "#79553a",
          600: "#604330",
          700: "#4d3526",
          800: "#3d2a1e",
          900: "#312218",
          950: "#1f140f",
        },
        olive: {
          50: "#fafdf5",
          100: "#e3edcd",
          200: "#ccdbae",
          300: "#b2c48c",
          400: "#99ad6b",
          500: "#7d9151",
          600: "#667741",
          700: "#515f34",
          800: "#3d4927",
          900: "#2f391d",
          950: "#1e2412",
        },
        // Semantic UI colors (simple direct class usage).
        production: "#216869",
        development: "#3B5BA0",
        testing: "#857D88",
        validation: "#A37C27",
        pass: "#166534",
        germline: "#B5761B",
        "germline-risk": "#9B3D12",
        warn: "#C17C00",
        fail: "#8C1D1D",
        tier1: "#D55E00",
        tier2: "#E69F00",
        tier3: "#0072B2",
        tier4: "#009E73",
        tier999: "#666666",
        tierother: "#999999",
        "tier-header1": "rgba(213, 94, 0, 0.5)",
        "tier-header2": "rgba(230, 159, 0, 0.5)",
        "tier-header3": "rgba(0, 114, 178, 0.5)",
        "tier-header4": "rgba(0, 158, 115, 0.5)",
        "tier-header999": "rgba(102, 102, 102, 0.5)",
        melanoma: "#fb6b6b",
        cns: "#76c7a6",
        lung: "#f57c94",
        colon: "#bbbbbb",
        gi: "#f8a488",
        dna: "#f5a25d",
        genelist: "#d1d2fa",
        fusionlist: "#ccf9d8",
        cnvlist: "#ffe3c2",
        panel: "#2563eb",
        wts: "#7c3aed",
        wgs: "#0f766e",
        unknown: "#6b7280",
      },
    },
  },
  safelist: [
    // Dynamic Jinja color classes (flash messages, role badges, etc).
    {
      pattern:
        /(bg|text|border|ring|from|to|via)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|brown|olive)-([0-9]{2,3})/,
      variants: ["hover", "focus"],
    },
    // Dynamic non-shaded classes like bg-{{ g_type }}.
    {
      pattern:
        /(bg|text|border|ring|from|to|via)-(black|white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|brown|olive)/,
      variants: ["hover", "focus"],
    },
    // Dynamic semantic classes from Python/Jinja (tiers, profiles, QC/hotspot badges).
    {
      pattern:
        /(bg|text|border|ring)-(production|validation|development|testing|pass|warn|fail|germline|germline-risk|tier1|tier2|tier3|tier4|tier999|tierother|tier-header1|tier-header2|tier-header3|tier-header4|tier-header999|melanoma|cns|lung|colon|gi|dna|genelist|fusionlist|cnvlist|panel|wts|wgs|unknown)/,
      variants: ["hover", "focus"],
    },
  ],
  plugins: [],
};
