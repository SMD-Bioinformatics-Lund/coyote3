(function (window) {
  "use strict";

  function toQuery(params) {
    if (!params) return "";
    var parts = [];
    Object.keys(params).forEach(function (key) {
      var value = params[key];
      if (value === undefined || value === null || value === "") return;
      parts.push(
        encodeURIComponent(key) + "=" + encodeURIComponent(String(value))
      );
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  async function parseBody(response) {
    var contentType = response.headers.get("content-type") || "";
    if (contentType.indexOf("application/json") !== -1) {
      return response.json();
    }
    return response.text();
  }

  async function request(path, options) {
    options = options || {};
    var method = options.method || "GET";
    var query = toQuery(options.query);
    var body = options.body;
    var headers = Object.assign(
      {
        "X-Requested-With": "XMLHttpRequest",
      },
      options.headers || {}
    );

    if (
      body &&
      typeof body === "object" &&
      !(body instanceof FormData) &&
      !(body instanceof URLSearchParams)
    ) {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
      body = JSON.stringify(body);
    }

    var apiBase = window.COYOTE_API_BASE || "/api";
    apiBase = String(apiBase).replace(/\/+$/, "");
    var cleanPath = String(path || "");
    if (!cleanPath.startsWith("/")) cleanPath = "/" + cleanPath;
    var url = apiBase + "/v1" + cleanPath + query;

    var response = await fetch(url, {
      method: method,
      headers: headers,
      body: body,
      credentials: "same-origin",
    });

    var payload = await parseBody(response);
    if (!response.ok) {
      var error = new Error(
        (payload && payload.error) || ("API request failed (" + response.status + ")")
      );
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  window.coyoteApi = {
    request: request,
    get: function (path, query) {
      return request(path, { method: "GET", query: query });
    },
    post: function (path, body) {
      return request(path, { method: "POST", body: body });
    },
  };
})(window);
