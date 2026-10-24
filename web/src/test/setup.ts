// Global test setup for Vitest.
// Registers jest-dom matchers (e.g. toBeInTheDocument) and cleans up the DOM
// between tests so each test starts from a clean render tree.
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});
