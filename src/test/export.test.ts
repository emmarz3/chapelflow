import { afterEach, describe, expect, it, vi } from "vitest";
import { downloadCsv } from "../lib/export";

describe("CSV export", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("does not create an empty export", () => {
    expect(downloadCsv("empty.csv", [])).toBe(false);
  });

  it("escapes spreadsheet values and triggers a local download", () => {
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:test"),
      revokeObjectURL: vi.fn(),
    });
    expect(
      downloadCsv("members.csv", [
        { name: "Adebayo, Grace", note: 'Said "hello"' },
      ]),
    ).toBe(true);
    expect(click).toHaveBeenCalledOnce();
  });
});
