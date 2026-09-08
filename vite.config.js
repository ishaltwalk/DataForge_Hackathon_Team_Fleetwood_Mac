import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// /api is proxied to the Flask process so the browser sees one origin.
// Without this the front end hardcoded http://localhost:8000, which broke
// CORS preflight on the multipart upload and broke entirely off localhost.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
