/// <reference types="vitest" />
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// The API key is read here, on the dev server, and added by the proxy.
// It never appears in client code or the built bundle.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, ".."), "");
  const proxy = {
    "/api": {
      target: "http://127.0.0.1:8000",
      changeOrigin: true,
      headers: { "X-API-Key": env.API_KEY ?? "" },
    },
  };
  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    preview: { port: 4173, proxy },
    test: { environment: "jsdom", include: ["tests/**/*.test.{ts,tsx}"] },
  };
});
