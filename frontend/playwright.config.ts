import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:3000", browserName: "chromium" },
  timeout: 180000,
  workers: 1,
});
