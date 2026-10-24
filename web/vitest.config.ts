import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

// Test configuration: jsdom environment + Testing Library matchers.
// The `test` npm script runs `vitest --run`, so the suite exits cleanly even
// with zero tests present.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: true,
      include: ["src/**/*.{test,spec}.{ts,tsx}"],
      // Scaffold convenience: an empty suite is a clean pass, so CI and
      // `npm run test` succeed before any tests exist.
      passWithNoTests: true,
    },
  })
);
