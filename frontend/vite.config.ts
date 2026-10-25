import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Django runs on :8000. Do NOT set changeOrigin: the Host header must stay
// localhost:5173 so that Django's CSRF Origin check on the login form passes.
const django = { target: 'http://localhost:8000' }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    proxy: {
      '/api': django,
      '/accounts': django,
      '/admin': django,
      '/static': django,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
