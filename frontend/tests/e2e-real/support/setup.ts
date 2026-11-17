// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { request, expect } from "@playwright/test"
import { stackState } from "./disposable-stack"

/** Create synthetic scoped accounts through the same public administration API. */
export default async function setup() {
  const state = stackState()
  const client = await request.newContext({ baseURL: state.baseURL })
  try {
    for (const [username, password] of [[state.username, state.password], [state.superuser, state.superuserPassword]]) {
      let login = await client.post("api/v1/auth/sessions", { data: { username, password, provider: "local" } })
      expect(login.status()).toBe(201)
      const data = await login.json()
      expect(data.user.must_change_password).toBe(true)
      const changed = await client.post("api/v1/auth/password/change", {
        data: { current_password: password, new_password: state.reviewPassword, confirm_password: state.reviewPassword },
        headers: { "X-CSRF-Token": data.csrf_token, Origin: new URL(state.baseURL).origin },
      })
      expect(changed.status()).toBe(200)
      login = await client.post("api/v1/auth/sessions", { data: { username, password: state.reviewPassword, provider: "local" } })
      expect(login.status()).toBe(201)
    }
    const csrf = await client.get("api/v1/auth/whoami")
    expect(csrf.ok()).toBe(true)
    for (const [username, role, environment] of [["browser.reviewer", "user", "testing"], ["browser.viewer", "viewer", "testing"], ["browser.no-scope", "user", "production"]]) {
      const response = await client.post("api/v1/users", {
        headers: { "X-CSRF-Token": (await csrf.json()).csrf_token, Origin: new URL(state.baseURL).origin },
        data: { form_data: { username, email: `${username}@example.test`, firstname: "Synthetic", lastname: "Reviewer", fullname: "Synthetic Reviewer", job_title: "Test account",
          roles: [role], auth_type: ["local"], password: state.reviewPassword, must_change_password: false,
          is_active: true, assay_access: [{ asp_id: "demo-hematology-training", environments: [environment] }] } },
      })
      expect(response.status(), `Create scoped account: ${await response.text()}`).toBe(201)
    }
  } finally { await client.dispose() }
}
