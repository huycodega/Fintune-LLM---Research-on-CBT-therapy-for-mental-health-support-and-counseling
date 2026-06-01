import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// User-facing app on port 5173.
// Frontend calls /api/* → proxied to FastAPI backend on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
