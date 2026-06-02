import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base is read from VITE_API_BASE at build/runtime; defaults to the
// local backend. In dev, the proxy below forwards /api and /ws to FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
