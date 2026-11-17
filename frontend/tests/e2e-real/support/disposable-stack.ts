// SPDX-FileCopyrightText: 2026 Ram Nanduri
// SPDX-License-Identifier: GPL-3.0-only

import { execFileSync } from "node:child_process"
import { lstatSync, readFileSync } from "node:fs"

export type StackState = {
  format: number; project: string; pid: number; created: number; baseURL: string
  databases: Record<string, string>; containers: Record<string, string>
  username: string; password: string; superuser: string; superuserPassword: string
  reviewPassword: string; dnaSample: string; rnaSample: string
}
const docker = ["--host", "unix:///var/run/docker.sock"]

/** Reject external endpoints and non-demo data before any browser request. */
export function validateState(state: StackState): void {
  const url = new URL(state.baseURL)
  if (state.format !== 1 || !/^coyote4-demo-[a-f0-9]{8}$/.test(state.project) ||
      url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port ||
      url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("Browser acceptance requires a generated local disposable stack.")
  }
  const databases = { COYOTE4_DB: "coyote4_demo", IDENTITY_DB: "coyote4_demo_identity",
    KNOWLEDGEBASE_DB: "coyote4_demo_knowledgebase", BAM_DB: "coyote4_demo_bam" }
  if (Object.keys(state.databases).length !== 4 || Object.entries(databases).some(([k, v]) => state.databases[k] !== v)) {
    throw new Error("Browser tests must never use production or ordinary deployment databases.")
  }
  if (!Number.isInteger(state.pid) || state.pid <= 1 || !Number.isFinite(state.created) ||
      Date.now() / 1000 - state.created > 7200 || state.created > Date.now() / 1000 + 5 ||
      ["frontend", "demo-mongo", "worker"].some(service => !/^[a-f0-9]{64}$/.test(state.containers[service] || "")) ||
      !state.username || !state.password || !state.reviewPassword ||
      state.dnaSample !== "DEMO_STARTER_DNA" || state.rnaSample !== "DEMO_STARTER_RNA") {
    throw new Error("Missing or expired disposable browser credentials and container identities.")
  }
}

function inspect(id: string) {
  return JSON.parse(execFileSync("docker", [...docker, "inspect", id], {
    encoding: "utf8", timeout: 15_000, stdio: ["ignore", "pipe", "pipe"],
  }))[0]
}

export function ownedContainer(state: StackState, service: string) {
  const id = state.containers[service]
  if (!id || !/^[a-f0-9]{64}$/.test(id)) throw new Error("Missing owned browser container.")
  const container = inspect(id)
  const labels = container.Config.Labels || {}
  if (labels["com.docker.compose.project"] !== state.project || labels["com.docker.compose.service"] !== service) {
    throw new Error("Container does not belong to this disposable browser run.")
  }
  return container
}

/** Accept only the live runner's owner-only proof; ordinary deployment variables are forbidden. */
export function stackState(environment = process.env): StackState {
  if (["COYOTE4_E2E_BASE_URL", "COYOTE4_E2E_USERNAME", "COYOTE4_E2E_PASSWORD", "COYOTE4_E2E_RELEASE", "COYOTE4_E2E_ALLOW_SELF_SIGNED"].some(name => environment[name])) {
    throw new Error("Existing deployment targets are forbidden. Use bash install.sh test-browser.")
  }
  const file = environment.COYOTE4_E2E_STATE
  if (!file) throw new Error("Use bash install.sh test-browser to create a disposable container stack.")
  const stat = lstatSync(file)
  if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077) || stat.uid !== process.getuid?.()) {
    throw new Error("Disposable browser state must be an owner-only regular file.")
  }
  const state = JSON.parse(readFileSync(file, "utf8")) as StackState
  validateState(state)
  process.kill(state.pid, 0)
  const frontend = ownedContainer(state, "frontend")
  const mongo = ownedContainer(state, "demo-mongo")
  const binding = frontend.NetworkSettings.Ports["3000/tcp"]
  if (!frontend.State.Running || !mongo.State.Running || binding?.length !== 1 ||
      binding[0].HostIp !== "127.0.0.1" || binding[0].HostPort !== new URL(state.baseURL).port ||
      Object.values(mongo.NetworkSettings.Ports).some(value => value !== null)) {
    throw new Error("Browser port must belong to the new stack; its database must not publish any port. " + JSON.stringify({ frontendRunning: frontend.State.Running, mongoRunning: mongo.State.Running, frontendPorts: frontend.NetworkSettings.Ports, frontendBinding: frontend.HostConfig.PortBindings, mongoPorts: mongo.NetworkSettings.Ports }))
  }
  return state
}

/** Pause delivery, not the API, to exercise durable ingestion recovery. */
export function setWorkerRunning(state: StackState, running: boolean): void {
  ownedContainer(state, "worker")
  execFileSync("docker", [...docker, running ? "start" : "stop", state.containers.worker], {
    timeout: 30_000, stdio: ["ignore", "pipe", "pipe"],
  })
}
