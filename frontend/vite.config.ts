import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: process.env.GITHUB_ACTIONS ? "/erp_system/" : "/",
  server: {
    allowedHosts: ["localhost", "127.0.0.1", "comp", "one", "spf-roc", "182.168.1.120"],
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
