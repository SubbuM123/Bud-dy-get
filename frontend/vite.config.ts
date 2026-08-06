/**
 * Vite build/dev-server configuration. Registers the React plugin, sets up the `@` path
 * alias to src/ (mirrored in tsconfig.json's `paths`) so imports can read `@/lib/utils`
 * instead of long relative paths, and proxies `/api` requests to the backend container so
 * the frontend can call the API with same-origin relative URLs during development.
 */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
