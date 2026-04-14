import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const STATIC_JS_DIR = resolve(__dirname, "..", "..", "..", "coyote", "static", "js");

/**
 * Load a vanilla JS file from coyote/static/js into the current jsdom window
 * by injecting it as a <script> element. This mirrors how the browser executes
 * classic scripts so function declarations and IIFEs behave the same way they
 * do in production.
 */
export function loadScript(filename, { exports = [] } = {}) {
  const fullPath = resolve(STATIC_JS_DIR, filename);
  const code = readFileSync(fullPath, "utf8");
  // jsdom executes injected <script> elements in a separate realm, so
  // assignments to `window` from inside the script don't reach the test's
  // `window`. Instead we evaluate the code as a Function body in the test's
  // own realm, passing `window` and `document` as parameters. Top-level
  // function declarations become locals; for any symbols a test wants to
  // call directly we append explicit `window.X = X` assignments.
  const tail = exports
    .map(
      (name) =>
        `if (typeof ${name} !== "undefined") { window.${name} = ${name}; }`,
    )
    .join("\n");
  // eslint-disable-next-line no-new-func
  const fn = new Function("window", "document", `${code}\n${tail}`);
  fn.call(window, window, document);
}
