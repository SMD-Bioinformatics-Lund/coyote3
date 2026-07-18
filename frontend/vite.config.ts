import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

function normalizeScriptName(value?: string) {
  const raw = String(value || '').trim()
  if (!raw || raw === '/') return ''
  return `/${raw.replace(/^\/+|\/+$/g, '')}`
}

const scriptName = normalizeScriptName(process.env.SCRIPT_NAME || process.env.VITE_SCRIPT_NAME)
const apiTarget = process.env.VITE_API_URL || 'http://coyote3_dev_api:8001'
const stripScriptName = (requestPath: string) =>
  scriptName ? requestPath.replace(new RegExp(`^${scriptName}(?=/)`), '') : requestPath

// https://vite.dev/config/
export default defineConfig({
  base: scriptName ? `${scriptName}/` : '/',
  plugins: [react(), tailwindcss()],
  define: {
    'import.meta.env.VITE_SCRIPT_NAME': JSON.stringify(scriptName),
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
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      ...(scriptName
        ? {
            [`${scriptName}/api`]: {
              target: apiTarget,
              changeOrigin: true,
              rewrite: stripScriptName,
            },
          }
        : {}),
    }
  }
})
