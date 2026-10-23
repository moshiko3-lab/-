import { defineConfig } from "@playwright/test";

// Smoke test of the real app in a browser, against the local dev server and the local Supabase.
export default defineConfig({
  testDir: "e2e",
  testMatch: "*.e2e.ts",
  workers: 1, // the tests share one database
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure" },
  webServer: { command: "npm run dev", url: "http://localhost:3000/login", reuseExistingServer: true },
});
