const { defineConfig } = require("vitest/config");
const path = require("path");

module.exports = defineConfig({
  test: {
    environment: "jsdom",
    include: [path.resolve(__dirname, "**/*.test.mjs")],
    globals: false,
    root: path.resolve(__dirname, "..", ".."),
  },
});
