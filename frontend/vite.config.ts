import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: process.env.GITHUB_ACTIONS ? "/erp_system/" : "/",
  server: {
    host: "0.0.0.0",
    // LAN / SSH host access (e.g. http://182.168.1.166:18082)
    allowedHosts: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
