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
    port: 5200,
    strictPort: true,
    allowedHosts: ['openbook.alexlee.ccwu.cc'],
    proxy: {
      '/api': {
        target: 'http://localhost:5201',
        changeOrigin: true,
      },
    },
  },
})
