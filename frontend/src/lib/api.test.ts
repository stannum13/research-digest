import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearSearchCache,
  deleteSearchCacheEntry,
  getSearchCacheStatus,
} from "./api";

let fetchMock: ReturnType<typeof vi.fn>;

function apiResponse(payload: unknown) {
  return {
    ok: true,
    json: async () => payload,
  };
}

describe("search cache API client", () => {
  beforeEach(() => {
    fetchMock = vi.fn(async () =>
      apiResponse({
        cache_version: "retrieval-search-v1",
        deleted_count: 1,
        total_entries: 1,
        total_hits: 2,
        entries: [],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the search cache status and maintenance endpoints with the expected methods", async () => {
    await getSearchCacheStatus();
    await clearSearchCache();
    await deleteSearchCacheEntry(11);

    const [statusUrl, statusInit] = fetchMock.mock.calls[0];
    expect(new URL(String(statusUrl)).pathname).toBe("/search/cache/status");
    expect(statusInit?.method).toBeUndefined();

    const [clearUrl, clearInit] = fetchMock.mock.calls[1];
    expect(new URL(String(clearUrl)).pathname).toBe("/search/cache");
    expect(clearInit?.method).toBe("DELETE");

    const [deleteUrl, deleteInit] = fetchMock.mock.calls[2];
    expect(new URL(String(deleteUrl)).pathname).toBe("/search/cache/11");
    expect(deleteInit?.method).toBe("DELETE");
  });
});
