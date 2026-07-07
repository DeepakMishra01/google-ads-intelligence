import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The backend (FastAPI) runs on :8000. In dev we proxy /api → backend so the
// browser talks to one origin (no CORS juggling). In production, set
// VITE_API_BASE or serve the built assets behind the same reverse proxy.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Split heavy vendors into cacheable chunks (Recharts is large).
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
          query: ["@tanstack/react-query", "axios"],
        },
      },
    },
  },
});
