import { defineConfig } from "vitest/config"

export default defineConfig({
  test: {
    globalSetup: "./tests/global-setup.ts",
    setupFiles: ["./tests/setup.ts"],
    testTimeout: 15_000,
    hookTimeout: 10_000,
    retry: 2,
    include: ["tests/**/*.e2e.ts", "tests/**/*.test.ts", "tests/**/*.spec.ts"],
    pool: "forks",
    poolOptions: {
      forks: {
        singleFork: true,
        isolate: false,
      },
    },
    sequence: {
      concurrent: false,
    },
  },
})
