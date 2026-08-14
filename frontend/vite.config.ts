import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'
import path from 'path'

function normalizeScriptName(value?: string) {
  const raw = String(value || '').trim()
  if (!raw || raw === '/') return ''
  return `/${raw.replace(/^\/+|\/+$/g, '')}`
}

const scriptName = normalizeScriptName(process.env.SCRIPT_NAME)
const apiTarget = process.env.COYOTE3_API_INTERNAL_URL || 'http://api:8001'
const organizationName = process.env.ORGANIZATION_NAME || 'Coyote3'
const localTimeZone = process.env.LOCAL_TIME_ZONE || process.env.TZ || 'UTC'
const stripScriptName = (requestPath: string) =>
  scriptName ? requestPath.replace(new RegExp(`^${scriptName}(?=/)`), '') : requestPath

function readAppVersion() {
  try {
    const versionFile = path.resolve(__dirname, '../api/version.py')
    const content = fs.readFileSync(versionFile, 'utf-8')
    return content.match(/__version__\s*=\s*["']([^"']+)["']/)?.[1] || 'v4.0.0-dev'
  } catch {
    return 'v4.0.0-dev'
  }
}

const appVersion = readAppVersion()

// https://vite.dev/config/
export default defineConfig({
  base: scriptName ? `${scriptName}/` : '/',
  plugins: [react(), tailwindcss()],
  define: {
    __COYOTE3_RUNTIME__: JSON.stringify({
      appVersion,
      gensUri: String(process.env.GENS_URI || '').trim().replace(/\/+$/, ''),
      igvUri: String(process.env.IGV_URI || '').trim().replace(/\/+$/, ''),
      localTimeZone,
      organizationName,
      scriptName,
    }),
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    allowedHosts: [
      'frontend',
      'localhost',
      '127.0.0.1',
      'host.docker.internal',
    ],
    proxy: {
      ...(scriptName
        ? {
            [`${scriptName}/api`]: {
              target: apiTarget,
              changeOrigin: true,
              rewrite: stripScriptName,
            },
          }
        : {
            '/api': {
              target: apiTarget,
              changeOrigin: true,
            },
          }),
    }
  }
})
