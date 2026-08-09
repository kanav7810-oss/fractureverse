import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to uvicorn so the app is single origin in development
// as well as in production, where api/main.py mounts app/dist at the site root.
// Without the backend running the proxy simply fails and the app falls into offline
// mode, which is a state the UI names on screen rather than hiding.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
