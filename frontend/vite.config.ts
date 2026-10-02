import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.EYES_API_PROXY_TARGET || "http://127.0.0.1:8000";
  const direct = { target, changeOrigin: true };
  const proxy = {
    "/openapi.json": direct,
    "/docs": direct,
    "/v1": direct,
    "/api": {
      target,
      changeOrigin: true,
      rewrite: (path: string) => path.replace(/^\/api/, ""),
    },
  };
  return {
    plugins: [react()],
    server: { proxy },
    preview: { proxy },
    build: { target: "es2022" },
  };
});
