import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// SPA dev server proxies API calls to the FastAPI backend so cookies are same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
