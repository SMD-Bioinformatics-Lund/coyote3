// Forward development UI output to the same internal syslog receiver as production Nginx.
import { spawn } from "node:child_process"
import { createSocket } from "node:dgram"
import { createInterface } from "node:readline"

const socket = createSocket("udp4")
socket.on("error", (error) => process.stderr.write(`UI log forwarding failed: ${error.message}\n`))
let pending = 0
let exited = false

function write(message, severity = "info") {
  pending += 1
  const priority = severity === "error" ? 187 : severity === "warning" ? 188 : 190
  const packet = Buffer.from(`<${priority}>ui: ${message}`).subarray(0, 60000)
  socket.send(packet, 5514, "monitor", (error) => {
    if (error) process.stderr.write(`UI log forwarding failed: ${error.message}\n`)
    pending -= 1
    if (exited && pending === 0) socket.close()
  })
}

const child = spawn(process.argv[2], process.argv.slice(3), { stdio: ["inherit", "pipe", "pipe"] })
for (const [stream, output] of [[child.stdout, process.stdout], [child.stderr, process.stderr]]) {
  createInterface({ input: stream }).on("line", (line) => {
    output.write(line + "\n")
    const severity = /\berror\b|\bfatal\b|\bfailed\b/i.test(line) ? "error"
      : /\bwarn(ing)?\b/i.test(line) ? "warning" : stream === child.stderr ? "error" : "info"
    write(line, severity)
  })
}
child.on("error", (error) => { write(error.message, "error"); process.exitCode = 1 })
child.on("close", (code, signal) => {
  if (code && code !== 0) write(`UI server exited with code ${code}`, "error")
  process.exitCode = code ?? (signal ? 1 : 0)
  exited = true
  if (pending === 0) socket.close()
})
for (const signal of ["SIGTERM", "SIGINT"]) process.on(signal, () => child.kill(signal))
