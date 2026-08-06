/**
 * Vitest configuration, kept separate from vite.config.ts so the dev-server proxy settings
 * there don't need to account for the test environment. Reuses the same `@` alias as the
 * app source so test files can import components the same way app code does.
 */
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
