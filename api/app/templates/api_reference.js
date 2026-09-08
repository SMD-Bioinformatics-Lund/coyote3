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
      SwaggerUIBundle({
        spec: schema,
        dom_id: "#api-renderer",
        deepLinking: true,
        filter: true,
        docExpansion: "list",
        defaultModelsExpandDepth: -1,
        displayRequestDuration: true,
        persistAuthorization: false,
        validatorUrl: null,
        tryItOutEnabled: false,
        requestInterceptor: (request) => {
          const token = document.getElementById("csrf-token").value.trim();
          const local = new URL(request.url, window.location.href).origin === window.location.origin;
          if (local && token && ["POST", "PUT", "PATCH", "DELETE"].includes(request.method.toUpperCase())) {
            request.headers["X-CSRF-Token"] = token;
          }
          return request;
        },
        supportedSubmitMethods: ["get", "post", "put", "patch", "delete"],
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout",
        onComplete: loaded,
      });
    }
  } catch { fail(); }
};
document.head.appendChild(script);
