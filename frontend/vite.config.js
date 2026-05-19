import { defineConfig } from "vite";

const backendTarget = process.env.VITE_BACKEND_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  server: {
    proxy: {
      "/health": backendTarget,
      "/claude": backendTarget,
      "/tasks": backendTarget,
    },
  },
});
