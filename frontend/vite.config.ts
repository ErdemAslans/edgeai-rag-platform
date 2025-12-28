import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    port: 3000,
    hmr: {
      overlay: false,
    },
    watch: {
      usePolling: true,
      interval: 1000,
    },
  },
})