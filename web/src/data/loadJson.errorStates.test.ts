// Feature: dashboard — example/unit tests for loadJson error-state mapping.
//
// These cover the four runtime failure modes the data layer must map to a
// typed `error` LoadState (Req 1.7, 3.2, 3.3), exercised across all six logical
// data files (what.json, investigate.json, evidence.json, where.json,
// sources.json, ma_counties.geojson):
//   1. network rejection (fetch rejects)          -> reason "network"
//   2. 404 / non-2xx (response.ok === false)      -> reason "network"
//   3. malformed JSON / wrong top-level shape     -> reason "parse"
//   4. >10 s timeout (AbortController aborts)      -> reason "timeout"
//
// In every case the returned state must be { status: "error", reason, file }
// and MUST name the file it failed on. `fetch` is always mocked — no real
// network I/O — and the timeout case uses fake timers so the suite never waits
// a real 10 seconds.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadJson, loadSources } from "./loadJson";
import {
  validateWhatEntry,
  validateInvestigateEntry,
  validateEvidenceEntry,
  validateWhereEntry,
} from "./validators";
import type { CountyFeature } from "./types";

/**
 * The AbortController timeout lives inside loadJson. For the array/object files
 * we pass each validator; ma_counties.geojson has no dedicated loader yet, so
 * per the task we exercise the same loadJson error path with a trivial guard —
 * the error mapping is identical and does not depend on the validator.
 */
const trivialGeoGuard = (value: unknown): value is CountyFeature =>
  typeof value === "object" && value !== null;

/** One descriptor per logical file and how it is loaded through the data layer. */
const FILES = [
  {
    file: "what.json",
    load: () => loadJson("what.json", validateWhatEntry),
    isArrayFile: true,
  },
  {
    file: "investigate.json",
    load: () => loadJson("investigate.json", validateInvestigateEntry),
    isArrayFile: true,
  },
  {
    file: "evidence.json",
    load: () => loadJson("evidence.json", validateEvidenceEntry),
    isArrayFile: true,
  },
  {
    file: "where.json",
    load: () => loadJson("where.json", validateWhereEntry),
    isArrayFile: true,
  },
  {
    // sources.json uses loadSources (validated as a single object).
    file: "sources.json",
    load: () => loadSources("sources.json"),
    isArrayFile: false,
  },
  {
    // ma_counties.geojson has no dedicated loader yet; exercise loadJson so the
    // geojson filename's error mapping is covered.
    file: "ma_counties.geojson",
    load: () => loadJson("ma_counties.geojson", trivialGeoGuard),
    isArrayFile: true,
  },
] as const;

/** Build a mock Response-like object for fetch. */
function mockResponse(opts: {
  ok: boolean;
  json: () => Promise<unknown>;
  status?: number;
}): Response {
  return {
    ok: opts.ok,
    status: opts.status ?? (opts.ok ? 200 : 404),
    json: opts.json,
  } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("loadJson / loadSources error-state mapping across the six data files", () => {
  describe("network rejection (fetch rejects) -> error reason 'network'", () => {
    it.each(FILES)("maps a fetch rejection for $file to network error", async ({ file, load }) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockRejectedValue(new TypeError("Failed to fetch"))
      );

      const state = await load();

      expect(state).toEqual({ status: "error", reason: "network", file });
      // No numbers / data ever ride along on an error state.
      expect(state).not.toHaveProperty("data");
    });
  });

  describe("404 / non-2xx (response.ok === false) -> error reason 'network'", () => {
    it.each(FILES)("maps a 404 for $file to network error", async ({ file, load }) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          mockResponse({
            ok: false,
            status: 404,
            json: () => Promise.resolve({}),
          })
        )
      );

      const state = await load();

      expect(state).toEqual({ status: "error", reason: "network", file });
      expect(state).not.toHaveProperty("data");
    });
  });

  describe("invalid JSON (response.json() throws) -> error reason 'parse'", () => {
    it.each(FILES)("maps unparseable JSON for $file to parse error", async ({ file, load }) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          mockResponse({
            ok: true,
            json: () => Promise.reject(new SyntaxError("Unexpected token")),
          })
        )
      );

      const state = await load();

      expect(state).toEqual({ status: "error", reason: "parse", file });
      expect(state).not.toHaveProperty("data");
    });
  });

  describe("wrong top-level shape -> error reason 'parse'", () => {
    // For the array files a non-array top-level body is the wrong shape; for
    // sources.json a body that fails validateSourcesData is the wrong shape.
    it.each(FILES)("maps a wrong top-level shape for $file to parse error", async ({ file, load, isArrayFile }) => {
      // Array files expect an array: hand them an object instead.
      // sources.json expects a valid SourcesData object: hand it a bare array,
      // which fails validateSourcesData.
      const wrongShapeBody: unknown = isArrayFile
        ? { not: "an array" }
        : ["not", "a", "sources", "object"];

      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          mockResponse({
            ok: true,
            json: () => Promise.resolve(wrongShapeBody),
          })
        )
      );

      const state = await load();

      expect(state).toEqual({ status: "error", reason: "parse", file });
      expect(state).not.toHaveProperty("data");
    });
  });

  describe("timeout > 10s (AbortController aborts) -> error reason 'timeout'", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it.each(FILES)("maps a timed-out fetch for $file to timeout error", async ({ file, load }) => {
      // Model a fetch that never resolves on its own but rejects (as a real
      // fetch does) when the AbortController signal fires — which loadJson's
      // internal 10 s timer triggers via controller.abort().
      vi.stubGlobal(
        "fetch",
        vi.fn(
          (_input: RequestInfo | URL, init?: RequestInit) =>
            new Promise<Response>((_resolve, reject) => {
              const signal = init?.signal;
              if (!signal) return;
              signal.addEventListener("abort", () => {
                reject(
                  Object.assign(new Error("The operation was aborted."), {
                    name: "AbortError",
                  })
                );
              });
            })
        )
      );

      const pending = load();
      // Advance past the 10 s abort timeout without waiting in real time; the
      // Async variant also flushes the microtasks that settle the rejection.
      await vi.advanceTimersByTimeAsync(10_000);

      const state = await pending;

      expect(state).toEqual({ status: "error", reason: "timeout", file });
      expect(state).not.toHaveProperty("data");
    });
  });
});
