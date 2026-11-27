import { readFile } from "node:fs/promises";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PDFDocument } from "pdf-lib";
import { buildPdf, downloadPdf } from "../lib/export";
import { downloadAuthenticatedPdf } from "../lib/api";

const regular = readFile("public/fonts/NotoSans-Regular.ttf");
const bold = readFile("public/fonts/NotoSans-Bold.ttf");

describe("PDF export", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("does not create an empty export", async () => {
    expect(await downloadPdf("empty.pdf", [])).toBe(false);
  });

  it("builds a valid multipage PDF with Unicode names and triggers a download", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
      ok: true,
      arrayBuffer: async () => Uint8Array.from(await (url.includes("Bold") ? bold : regular)).buffer,
    })));
    const rows = Array.from({ length: 45 }, (_, i) => ({ name: `Chinólú ${i}`, note: 'Said "hello"', level: "400" }));
    const bytes = await buildPdf("members.pdf", rows, { title: "Member directory" });
    expect(new TextDecoder().decode(bytes.slice(0, 8))).toBe("%PDF-1.7");
    expect((await PDFDocument.load(bytes)).getPageCount()).toBeGreaterThan(1);

    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.isConnected).toBe(true);
    });
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:test"), revokeObjectURL: vi.fn() });
    expect(await downloadPdf("members.pdf", rows)).toBe(true);
    expect(click).toHaveBeenCalledOnce();
  });

  it("downloads an authorized server PDF using DRF-compatible content negotiation", async () => {
    const pdf = new Blob(["%PDF-test"], { type: "application/pdf" });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain("/members/export-pdf/");
      expect(new Headers(init?.headers).get("Accept")).toBe("*/*");
      return new Response(pdf, { headers: { "Content-Type": "application/pdf" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:server-pdf"), revokeObjectURL: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.isConnected).toBe(true);
      expect(this.download).toBe("chapelflow-members.pdf");
    });
    await downloadAuthenticatedPdf("/members/export-pdf/", "chapelflow-members.pdf");
    expect(fetchMock).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(document.querySelector('a[href="blob:server-pdf"]')).toBeNull();
  });
});
