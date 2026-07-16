import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
        target: process.env.VITE_API_URL || 'http://coyote3_dev_api:8001',
        changeOrigin: true,
      }
    }
  }
})
