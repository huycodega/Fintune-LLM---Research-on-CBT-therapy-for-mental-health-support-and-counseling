import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Clinician/admin app on port 5174 (different from user app's 5173).
// Same backend (FastAPI on :8000) — proxied via /api/*.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
