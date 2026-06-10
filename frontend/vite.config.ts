/// <reference types="vitest" />
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import wasm from 'vite-plugin-wasm'
import topLevelAwait from 'vite-plugin-top-level-await'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue(),
    wasm(),
    topLevelAwait({
      // The WASM wrapper from vite-plugin-wasm uses top-level await.
      // Must transform node_modules because codemirror-lang-typst lives there.
      filter: /\.(?:m?js|ts)$/,
    }),
  ],
  optimizeDeps: {
    exclude: ['@tauri-apps/api', 'codemirror-lang-typst'],
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  // Ensure modern browser compatibility for WASM and top-level await
  build: {
    target: 'esnext',
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
})
