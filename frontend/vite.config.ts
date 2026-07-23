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

const scriptName = normalizeScriptName(process.env.SCRIPT_NAME || process.env.VITE_SCRIPT_NAME)
const apiTarget = process.env.VITE_API_URL || 'http://coyote3_dev_api:8001'
const organizationName = process.env.ORGANIZATION_NAME || process.env.VITE_ORGANIZATION_NAME || 'Coyote3'
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

const appVersion = process.env.VITE_APP_VERSION || readAppVersion()

// https://vite.dev/config/
export default defineConfig({
  base: scriptName ? `${scriptName}/` : '/',
  plugins: [react(), tailwindcss()],
  define: {
    'import.meta.env.VITE_SCRIPT_NAME': JSON.stringify(scriptName),
    'import.meta.env.VITE_ORGANIZATION_NAME': JSON.stringify(organizationName),
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(appVersion),
    'import.meta.env.VITE_LOCAL_TIME_ZONE': JSON.stringify(localTimeZone),
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
