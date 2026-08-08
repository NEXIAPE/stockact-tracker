import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El frontend habla con el backend local. Nada sale a internet desde aquí:
// todas las llamadas a fuentes de datos las hace el backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
