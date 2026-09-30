const loading = document.getElementById("docs-loading");
const error = document.getElementById("docs-error");
const fail = () => { loading.hidden = true; error.hidden = false; };
const loaded = () => { loading.hidden = true; };
const script = document.createElement("script");
script.src = view === "reference"
  ? "https://cdn.jsdelivr.net/npm/redoc@2.5.3/bundles/redoc.standalone.js"
  : "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.32.15/swagger-ui-bundle.js";
script.onerror = fail;
script.onload = async () => {
  try {
    const response = await fetch(schemaUrl, { credentials: "same-origin" });
    if (!response.ok) throw new Error("Schema unavailable");
    const schema = await response.json();
    if (view === "reference") {
      const tokens = getComputedStyle(document.documentElement);
      // ReDoc's color utilities require RGB; let the browser resolve our OKLCH tokens.
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      const context = canvas.getContext("2d");
      const color = (name) => {
        context.fillStyle = tokens.getPropertyValue(name).trim();
        context.fillRect(0, 0, 1, 1);
        const [r, g, b] = context.getImageData(0, 0, 1, 1).data;
        return `rgb(${r}, ${g}, ${b})`;
      };
      Redoc.init(schema, {
        hideDownloadButton: true,
        disableGoogleFont: true,
        requiredPropsFirst: true,
        pathInMiddlePanel: true,
        expandResponses: "200,201",
        nativeScrollbars: true,
        theme: {
          spacing: { sectionHorizontal: 28, sectionVertical: 24 },
          colors: { primary: { main: color("--accent") }, text: { primary: color("--ink"), secondary: color("--ink-muted") } },
          typography: { fontSize: "14px", fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", headings: { fontFamily: "inherit", fontWeight: "600" }, code: { fontSize: "12px", color: color("--ink"), backgroundColor: color("--surface-muted") } },
          sidebar: { width: "240px", backgroundColor: color("--surface-muted"), textColor: color("--ink-muted"), activeTextColor: color("--accent") },
          rightPanel: { backgroundColor: color("--code-surface"), textColor: color("--code-ink") },
        },
      }, document.getElementById("api-renderer"), (err) => err ? fail() : loaded());
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
      await loadBrowserSession();
      const explorer = SwaggerUIBundle({
        spec: schema,
        dom_id: "#api-renderer",
        deepLinking: true,
        filter: true,
        docExpansion: "list",
        defaultModelsExpandDepth: -1,
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
        layoutActions.scrollTo(resourceKey);
        // An already-open group may not rerender, so its scroll callback will not run.
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
