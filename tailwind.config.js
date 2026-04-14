/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./coyote/templates/**/*.html",
    "./coyote/blueprints/**/templates/**/*.html",
    "./coyote/blueprints/**/templates/**/*.jinja",
    "./coyote/blueprints/**/templates/partials/*.jinja",
    "./coyote/blueprints/**/templates/**/*.jinja2",
    "./coyote/static/js/**/*.js",
    "./coyote/**/*.py",
  ],
  theme: {
    extend: {},
  },
  safelist: [
    // Dynamic Jinja color classes (flash messages, role badges, etc).
    {
      pattern:
        /(bg|text|border|ring|from|to|via)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|brown|olive|sage|sand|mist)-([0-9]{2,3})/,
      variants: ["hover", "focus"],
    },
    // Dynamic non-shaded classes like bg-{{ g_type }}.
    {
      pattern:
        /(bg|text|border|ring|from|to|via)-(black|white|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|brown|olive|sage|sand|mist)/,
      variants: ["hover", "focus"],
    },
    // Dynamic semantic classes from Python/Jinja (tiers, profiles, QC/hotspot badges).
    {
      pattern:
        /(bg|text|border|ring|from|to|via)-(production|validation|development|testing|pass|warn|fail|germline|germline-risk|tier1|tier2|tier3|tier4|tier999|tierother|tier-header1|tier-header2|tier-header3|tier-header4|tier-header999|melanoma|cns|lung|colon|gi|dna|rna|genelist|fusionlist|cnvlist|panel|wts|wgs|unknown)/,
      variants: ["hover", "focus"],
    },
  ],
  plugins: [],
};
