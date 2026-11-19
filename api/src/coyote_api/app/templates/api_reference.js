// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

const themeToggle = document.getElementById("theme-toggle");
const syncThemeControl = () => {
  const dark = document.documentElement.classList.contains("dark");
  themeToggle.setAttribute("aria-pressed", String(dark));
  themeToggle.setAttribute("aria-label", dark ? "Use light theme" : "Use dark theme");
  themeToggle.textContent = dark ? "Light theme" : "Dark theme";
};
syncThemeControl();
themeToggle.addEventListener("click", () => {
  const dark = document.documentElement.classList.toggle("dark");
  try {
    localStorage.setItem("coyote4-docs-theme", dark ? "dark" : "light");
  } catch { /* Theme switching remains available without browser storage. */ }
  syncThemeControl();
});
const loading = document.getElementById("docs-loading");
const error = document.getElementById("docs-error");
const fail = () => { loading.hidden = true; error.hidden = false; };
const loaded = () => { loading.hidden = true; };
// The portal shell renders from its inline styles while Swagger's assets load.
// The portal styles are scoped outside the vendor-rendered content.
const stylesReady = view === "explorer" ? new Promise((resolve) => {
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.32.15/swagger-ui.css";
  stylesheet.onload = () => resolve(true);
  stylesheet.onerror = () => { fail(); resolve(false); };
  document.head.insertBefore(stylesheet, document.querySelector("style"));
}) : Promise.resolve(true);
// Fetch the contract while the renderer downloads. Neither needs to wait for login.
const schemaRequest = fetch(schemaUrl, { credentials: "same-origin" })
  .then((response) => {
    if (!response.ok) throw new Error("Schema unavailable");
    return response.json();
  })
  .catch(() => { fail(); return null; });
const script = document.createElement("script");
script.src = view === "reference"
  ? "https://cdn.jsdelivr.net/npm/redoc@2.5.3/bundles/redoc.standalone.js"
  : "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.32.15/swagger-ui-bundle.js";
script.onerror = fail;
script.onload = async () => {
  try {
    const schema = await schemaRequest;
    if (!schema || !await stylesReady) return;
    if (view === "reference") {
      const methods = new Set(["get", "post", "put", "patch", "delete", "options", "head", "trace"]);
      const resources = new Map();
      const operationResources = new Map();
      for (const item of Object.values(schema.paths || {})) {
        for (const [method, operation] of Object.entries(item)) {
          if (!methods.has(method)) continue;
          if (operation.operationId) operationResources.set(operation.operationId, operation.tags?.[0] || "default");
          for (const tag of operation.tags?.length ? operation.tags : ["default"]) {
            resources.set(tag, (resources.get(tag) || 0) + 1);
          }
        }
      }
      const select = document.getElementById("reference-resource");
      const orderedTags = [...new Set([
        ...(schema["x-tagGroups"] || []).flatMap((group) => group.tags),
        ...resources.keys(),
      ])].filter((tag) => resources.has(tag));
      for (const tag of orderedTags) {
        const option = document.createElement("option");
        option.value = tag;
        option.textContent = `${tag} (${resources.get(tag)} endpoints)`;
        select.append(option);
      }
      // ReDoc's tag anchors replace spaces and punctuation with URL-safe names.
      const tagId = (tag) => tag.replace(/&/g, "and").replace(/\s+/g, "-");
      let activeResource;
      const resourceFromHash = () => {
        // Explicit resource selection wins over hashes changed by ReDoc's scroll spy.
        const selected = new URLSearchParams(location.search).get("resource");
        if (resources.has(selected)) return selected;
        try {
          const operation = location.hash.match(/(?:^#|\/)operation\/([^/]+)/);
          if (operation) {
            const tag = operationResources.get(decodeURIComponent(operation[1]));
            if (tag) return tag;
          }
          const match = location.hash.match(/^#tag\/([^/]+)/);
          if (match) {
            const name = decodeURIComponent(match[1]);
            const tag = orderedTags.find((tag) => tag === name || tagId(tag) === name);
            if (tag) return tag;
          }
        } catch { return orderedTags[0]; }
        return activeResource || orderedTags[0];
      };
      const renderReference = () => {
        activeResource = resourceFromHash();
        select.value = activeResource;
        // ReDoc updates hashes while scrolling; keep resource selection across reloads.
        const address = new URL(location.href);
        address.searchParams.set("resource", activeResource);
        history.replaceState(null, "", address);
        loading.hidden = false;
        error.hidden = true;
        // Render one resource at a time; the downloaded OpenAPI contract stays complete.
        const paths = {};
        for (const [path, item] of Object.entries(schema.paths || {})) {
          const entries = Object.entries(item).filter(([method, operation]) =>
            !methods.has(method) || (operation.tags?.length ? operation.tags : ["default"]).includes(activeResource));
          if (entries.some(([method]) => methods.has(method))) paths[path] = Object.fromEntries(entries);
        }
        const resourceSchema = {
          ...schema,
          paths,
          tags: (schema.tags || []).filter((tag) => tag.name === activeResource),
          "x-tagGroups": [{ name: "API resource", tags: [activeResource] }],
        };
        Redoc.init(resourceSchema, {
          hideDownloadButton: true,
          disableGoogleFont: true,
          requiredPropsFirst: true,
          pathInMiddlePanel: true,
          expandResponses: "",
          schemasExpansionLevel: 1,
          jsonSamplesExpandLevel: 1,
          generatedSamplesMaxDepth: 3,
          nativeScrollbars: true,
        }, document.getElementById("api-renderer"), (err) => err ? fail() : loaded());
      };
      renderReference();
      window.addEventListener("hashchange", () => {
        if (resourceFromHash() !== activeResource) renderReference();
      });
      window.addEventListener("popstate", () => {
        if (resourceFromHash() !== activeResource) renderReference();
      });
      select.addEventListener("change", () => {
        const address = new URL(location.href);
        address.searchParams.set("resource", select.value);
        address.hash = `tag/${tagId(select.value)}`;
        history.pushState(null, "", address);
        renderReference();
      });
    } else {
      const navigation = document.getElementById("resource-navigation");
      const counts = new Map();
      let endpointCount = 0;
      for (const item of Object.values(schema.paths || {})) {
        for (const [method, operation] of Object.entries(item)) {
          if (!["get", "post", "put", "patch", "delete", "options", "head", "trace"].includes(method)) continue;
          endpointCount += 1;
          for (const tag of operation.tags?.length ? operation.tags : ["default"]) {
            counts.set(tag, (counts.get(tag) || 0) + 1);
          }
        }
      }
      document.getElementById("endpoint-count").textContent = `${endpointCount} endpoints`;
      const groups = [...(schema["x-tagGroups"] || [])];
      const grouped = new Set(groups.flatMap((group) => group.tags));
      const remaining = [...counts.keys()].filter((tag) => !grouped.has(tag));
      if (remaining.length) groups.push({ name: "Other resources", tags: remaining });
      for (const group of groups) {
        const section = document.createElement("section");
        const heading = document.createElement("h2");
        heading.textContent = group.name;
        section.append(heading);
        for (const tag of group.tags) {
          if (!counts.has(tag)) continue;
          const link = document.createElement("a");
          link.href = `#/${encodeURIComponent(tag)}`;
          link.dataset.resource = tag.toLowerCase();
          link.dataset.tag = tag;
          const label = document.createElement("span");
          label.textContent = tag;
          const count = document.createElement("span");
          count.className = "resource-count";
          count.textContent = counts.get(tag);
          link.append(label, count);
          section.append(link);
        }
        if (section.querySelector("a")) navigation.append(section);
      }
      const markActiveResource = () => {
        for (const link of navigation.querySelectorAll("a")) {
          const active = location.hash === link.hash || location.hash.startsWith(`${link.hash}/`);
          if (active) link.setAttribute("aria-current", "location");
          else link.removeAttribute("aria-current");
        }
      };
      window.addEventListener("hashchange", markActiveResource);
      markActiveResource();
      document.getElementById("resource-search").addEventListener("input", (event) => {
        const query = event.target.value.trim().toLowerCase();
        for (const section of navigation.children) {
          for (const link of section.querySelectorAll("a")) link.hidden = !link.dataset.resource.includes(query);
          section.hidden = !section.querySelector("a:not([hidden])");
        }
        document.getElementById("resource-empty").hidden = !!navigation.querySelector("a:not([hidden])");
      });
      const csrfInput = document.getElementById("csrf-token");
      const csrfHelp = document.getElementById("csrf-help");
      const loadBrowserSession = async () => {
        try {
          const url = new URL(schemaUrl, window.location.href);
          url.pathname = url.pathname.replace(/\/openapi\.json$/, "/auth/whoami");
          if (url.origin !== window.location.origin) return;
          const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
          if (!response.ok) return;
          const session = await response.json();
          if (session.csrf_token) {
            csrfInput.value = session.csrf_token;
            csrfHelp.textContent = `Using the browser session for ${session.username}. CSRF protection is configured automatically. No cookie or bearer token needs to be pasted into Authorize.`;
          }
        } catch {
          // Public documentation remains usable without a signed-in session.
        }
      };
      void loadBrowserSession();
      const explorer = SwaggerUIBundle({
        spec: schema,
        dom_id: "#api-renderer",
        deepLinking: true,
        filter: true,
        // Native Swagger default: open resource groups, collapse request details.
        docExpansion: "list",
        defaultModelsExpandDepth: -1,
        defaultModelExpandDepth: 1,
        syntaxHighlight: { activated: false },
        displayRequestDuration: true,
        persistAuthorization: false,
        withCredentials: true,
        validatorUrl: null,
        tryItOutEnabled: false,
        requestInterceptor: async (request) => {
          const local = new URL(request.url, window.location.href).origin === window.location.origin;
          const bearer = Object.keys(request.headers || {}).some((key) => key.toLowerCase() === "authorization");
          if (local && !bearer && ["POST", "PUT", "PATCH", "DELETE"].includes(request.method.toUpperCase())) {
            await loadBrowserSession();
            const token = csrfInput.value.trim();
            if (token) request.headers["X-CSRF-Token"] = token;
          }
          return request;
        },
        supportedSubmitMethods: ["get", "post", "put", "patch", "delete"],
        presets: [SwaggerUIBundle.presets.apis],
        plugins: [() => ({
          wrapComponents: {
            InfoContainer: () => () => null,
          },
        })],
        layout: "BaseLayout",
        onComplete: loaded,
      });
      navigation.addEventListener("click", (event) => {
        const link = event.target.closest("a[data-tag]");
        if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        const { layoutActions } = explorer.getSystem();
        const resourceKey = ["operations-tag", link.dataset.tag];
        layoutActions.updateFilter("");
        layoutActions.show(resourceKey, true);
        if (location.hash !== link.hash) history.pushState(null, "", link.href);
        // Own scrolling here: Swagger's animated scroll can finish after a viewport
        // resize and override this position. Repeated selections need no rerender.
        requestAnimationFrame(() => {
          const heading = [...document.querySelectorAll("#api-renderer .opblock-tag")]
            .find((element) => element.dataset.tag === link.dataset.tag);
          if (heading) {
            heading.scrollIntoView({ block: "start" });
            heading.tabIndex = -1;
            heading.focus({ preventScroll: true });
          }
        });
        markActiveResource();
      });
    }
  } catch { fail(); }
};
document.head.appendChild(script);
