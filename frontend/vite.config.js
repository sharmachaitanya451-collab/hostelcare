import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    allowedHosts: [
      'calculators-levitra-smooth-furnished.trycloudflare.com',
      'median-let-horn-cleanup.trycloudflare.com',
    ],
    // Same-origin in dev: /api and health checks are proxied to Flask.
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/healthz': 'http://127.0.0.1:5000',
      '/readyz': 'http://127.0.0.1:5000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
  },
})
