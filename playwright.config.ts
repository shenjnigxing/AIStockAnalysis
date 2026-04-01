import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:3000"
  },
  webServer: {
    command: "npm --prefix apps/web run dev",
    url: "http://localhost:3000",
    timeout: 120_000,
    reuseExistingServer: true
  }
});
