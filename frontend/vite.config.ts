import { resolve } from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export const server = {
  host: 'localhost',
  port: 3000,
  strictPort: true,
  proxy: {
    '/api/v1': {
      target: process.env.SPENDWISE_E2E_UPSTREAM ?? 'http://127.0.0.1:8000',
      changeOrigin: false,
    },
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': resolve(import.meta.dirname ?? process.cwd(), 'src') } },
  server,
  build: { manifest: true },
  test: { environment: 'jsdom', environmentOptions: { jsdom: { url: 'http://localhost:3000' } }, setupFiles: ['./src/test/setup.ts'], exclude: ['**/node_modules/**', '**/e2e/**', '**/dist/**'] },
})
