// Example/unit tests for the React Context data layer (Req 3.1, 3.2, 3.3, 3.5,
// 2.7, 16.3). No real network: `fetch` is mocked in every test.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import {
  WhatDataProvider,
  useWhatData,
  SourcesProvider,
  useSources,
  useIsSample,
  CountyBoundariesProvider,
  useCountyBoundaries,
} from "./providers";
import { LoadStateView } from "../components/LoadStateView";

/** Build a Response-like object good enough for loadJson / the geojson loader. */
function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    json: async () => body,
  } as unknown as Response;
}

/** A minimal valid WhatEntry used across the What provider tests. */
const validWhat = {
  condition: "Asthma",
  measure_id: "CASTHMA",
  low: 1,
  mid: 2,
  high: 3,
  t: 5,
  affected_adults: 1000,
  p_low: 0.1,
  p_high: 0.2,
  ctgov_url: "https://clinicaltrials.gov/search",
};

/** A minimal valid CountyFeature used by the boundaries tests. */
const validFeature = {
  type: "Feature",
  properties: { county_fips: "25025" },
  geometry: { type: "Polygon", coordinates: [[[0, 0]]] },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("WhatDataProvider / useWhatData", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  function WhatProbe() {
    const state = useWhatData();
    return (
      <LoadStateView state={state}>
        {(data) => <span data-testid="count">{data.length}</span>}
      </LoadStateView>
    );
  }

  it("starts in the loading state, then resolves to ready", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse([validWhat])
    );

    render(
      <WhatDataProvider>
        <WhatProbe />
      </WhatDataProvider>
    );

    // Initial LoadState is loading (Req 3.2).
    expect(screen.getByRole("status")).toHaveTextContent(/loading/i);

    await waitFor(() =>
      expect(screen.getByTestId("count")).toHaveTextContent("1")
    );
  });

  it("fetches its file exactly once per mount (Req 16.3)", async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValue(jsonResponse([validWhat]));

    render(
      <WhatDataProvider>
        <WhatProbe />
        <WhatProbe />
      </WhatDataProvider>
    );

    await waitFor(() =>
      expect(screen.getAllByTestId("count")[0]).toHaveTextContent("1")
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/data/what.json",
      expect.anything()
    );
  });

  it("maps a network failure to the unavailable message naming the file", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("offline")
    );

    render(
      <WhatDataProvider>
        <WhatProbe />
      </WhatDataProvider>
    );

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /This data is currently unavailable \(what\.json\)/i
      )
    );
  });

  it("maps an all-invalid array to the empty message", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse([{ not: "valid" }])
    );

    render(
      <WhatDataProvider>
        <WhatProbe />
      </WhatDataProvider>
    );

    await waitFor(() =>
      expect(screen.getByText(/No valid data is available/i)).toBeInTheDocument()
    );
  });

  it("throws a clear error when the hook is used outside its provider", () => {
    // Silence the expected React error boundary console noise.
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useWhatData())).toThrow(
      /must be used within a WhatDataProvider/
    );
    spy.mockRestore();
  });
});

describe("SourcesProvider / useSources / useIsSample", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  const sources = {
    data_as_of: "2024-01-01",
    sources: [
      { name: "CDC PLACES", url: "https://www.cdc.gov/", fetched: "2024-01-01" },
    ],
  };

  function wrapper({ children }: { children: ReactNode }) {
    return <SourcesProvider>{children}</SourcesProvider>;
  }

  it("useIsSample is true only when sources.json is flagged is_sample", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse({ ...sources, is_sample: true })
    );

    const { result } = renderHook(
      () => ({ sources: useSources(), isSample: useIsSample() }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.sources.status).toBe("ready"));
    expect(result.current.isSample).toBe(true);
  });

  it("useIsSample is false only for loaded sources with is_sample: false (Req 20.5)", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse({ ...sources, is_sample: false })
    );
    const { result } = renderHook(() => useIsSample(), { wrapper });
    await waitFor(() => expect(result.current).toBe(false));
  });

  it("useIsSample is true when is_sample is absent (cautious, Req 20.5)", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse(sources)
    );
    const { result } = renderHook(
      () => ({ sources: useSources(), isSample: useIsSample() }),
      { wrapper }
    );
    await waitFor(() => expect(result.current.sources.status).toBe("ready"));
    expect(result.current.isSample).toBe(true);
  });

  it("useIsSample is true while sources.json is not loaded yet (Req 20.5)", () => {
    // The fetch never settles, so Sources_Data stays in the loading state.
    (fetch as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      new Promise<Response>(() => {})
    );
    const { result } = renderHook(
      () => ({ sources: useSources(), isSample: useIsSample() }),
      { wrapper }
    );
    expect(result.current.sources.status).toBe("loading");
    expect(result.current.isSample).toBe(true);
  });

  it("useIsSample is true when sources.json fails to load (Req 20.5)", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("network down")
    );
    const { result } = renderHook(
      () => ({ sources: useSources(), isSample: useIsSample() }),
      { wrapper }
    );
    await waitFor(() => expect(result.current.sources.status).toBe("error"));
    expect(result.current.isSample).toBe(true);
  });
});

describe("CountyBoundariesProvider / useCountyBoundaries", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  function wrapper({ children }: { children: ReactNode }) {
    return <CountyBoundariesProvider>{children}</CountyBoundariesProvider>;
  }

  it("loads a FeatureCollection, omitting invalid features", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse({
        type: "FeatureCollection",
        features: [validFeature, { type: "Feature" }],
      })
    );

    const { result } = renderHook(() => useCountyBoundaries(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe("ready"));
    if (result.current.status === "ready") {
      expect(result.current.data).toHaveLength(1);
      expect(result.current.omittedCount).toBe(1);
    }
  });

  it("maps a non-FeatureCollection shape to a parse error naming the file", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse({ type: "Nope" })
    );

    const { result } = renderHook(() => useCountyBoundaries(), { wrapper });

    await waitFor(() => expect(result.current.status).toBe("error"));
    if (result.current.status === "error") {
      expect(result.current.reason).toBe("parse");
      expect(result.current.file).toBe("ma_counties.geojson");
    }
  });
});
