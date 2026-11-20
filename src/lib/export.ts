import type { PDFFont, PDFPage } from "pdf-lib";

type Column = { key: string; label: string };
type PdfOptions = { title?: string; subtitle?: string; columns?: Column[] };

function readable(key: string) {
  return key.replace(/([a-z])([A-Z])/g, "$1 $2").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function display(value: unknown): string {
  if (value == null || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function wrap(text: string, font: PDFFont, size: number, width: number): string[] {
  const lines: string[] = [];
  for (const paragraph of text.replace(/\r/g, "").split("\n")) {
    let line = "";
    for (const token of paragraph.split(/(\s+)/)) {
      if (font.widthOfTextAtSize(line + token, size) <= width) {
        line += token;
      } else {
        if (line.trim()) lines.push(line.trim());
        line = "";
        for (const char of token) {
          if (font.widthOfTextAtSize(line + char, size) > width && line) {
            lines.push(line);
            line = "";
          }
          line += char;
        }
      }
    }
    lines.push(line.trim());
  }
  return lines;
}

export async function buildPdf(filename: string, rows: Record<string, unknown>[], options: PdfOptions = {}) {
  const [{ PDFDocument, rgb }, { default: fontkit }] = await Promise.all([
    import("pdf-lib"), import("@pdf-lib/fontkit"),
  ]);
  const pdf = await PDFDocument.create();
  pdf.registerFontkit(fontkit);
  const [regular, bold] = await Promise.all([
    fetch("/fonts/NotoSans-Regular.ttf").then((response) => {
      if (!response.ok) throw new Error("PDF font could not be loaded.");
      return response.arrayBuffer();
    }),
    fetch("/fonts/NotoSans-Bold.ttf").then((response) => {
      if (!response.ok) throw new Error("PDF font could not be loaded.");
      return response.arrayBuffer();
    }),
  ]);
  const bodyFont = await pdf.embedFont(regular, { subset: true });
  const headingFont = await pdf.embedFont(bold, { subset: true });
  const columns = options.columns ?? [...new Set(rows.flatMap((row) => Object.keys(row)))].map((key) => ({ key, label: readable(key) }));
  const width = 842;
  const height = 595;
  const margin = 42;
  const fieldWidth = width - margin * 2 - 155;
  let page: PDFPage;
  let y = 0;
  const pages: PDFPage[] = [];
  const addPage = () => {
    page = pdf.addPage([width, height]);
    pages.push(page);
    page.drawRectangle({ x: 0, y: height - 88, width, height: 88, color: rgb(0.25, 0.14, 0.38) });
    page.drawText("CHRISLAND UNIVERSITY CHAPEL", { x: margin, y: height - 31, font: headingFont, size: 10, color: rgb(1, 1, 1) });
    page.drawText(options.title || readable(filename.replace(/\.pdf$/i, "").replace(/^chapelflow-/, "")), { x: margin, y: height - 57, font: headingFont, size: 16, color: rgb(1, 1, 1) });
    const meta = `${rows.length} records  •  ${new Date().toLocaleString("en-NG")}  •  ${options.subtitle || "Authorized dashboard export"}`;
    page.drawText(wrap(meta, bodyFont, 8, width - 2 * margin)[0] || "", { x: margin, y: height - 76, font: bodyFont, size: 8, color: rgb(0.9, 0.86, 0.94) });
    y = height - 112;
  };
  addPage();
  const ensure = (space: number) => { if (y - space < 50) addPage(); };
  rows.forEach((row, index) => {
    ensure(36);
    page.drawRectangle({ x: margin, y: y - 25, width: width - margin * 2, height: 29, color: rgb(0.95, 0.93, 0.97) });
    page.drawText(`Record ${index + 1}`, { x: margin + 10, y: y - 16, font: headingFont, size: 10, color: rgb(0.25, 0.14, 0.38) });
    y -= 36;
    columns.forEach(({ key, label }) => {
      const lines = wrap(display(row[key]), bodyFont, 8.5, fieldWidth - 10);
      lines.forEach((line, lineIndex) => {
        ensure(16);
        if (lineIndex === 0) page.drawText(label, { x: margin + 8, y, font: headingFont, size: 8, color: rgb(0.31, 0.27, 0.37) });
        page.drawText(line, { x: margin + 155, y, font: bodyFont, size: 8.5, color: rgb(0.15, 0.14, 0.18) });
        y -= 14;
      });
      y -= 4;
    });
    y -= 14;
  });
  pages.forEach((item, index) => {
    item.drawLine({ start: { x: margin, y: 39 }, end: { x: width - margin, y: 39 }, thickness: 0.6, color: rgb(0.8, 0.76, 0.84) });
    item.drawText("ChapelFlow  •  Confidential data export", { x: margin, y: 24, font: bodyFont, size: 8, color: rgb(0.42, 0.37, 0.47) });
    item.drawText(`Page ${index + 1} of ${pages.length}`, { x: width - margin - 80, y: 24, font: bodyFont, size: 8, color: rgb(0.42, 0.37, 0.47) });
  });
  return pdf.save();
}

export async function downloadPdf(filename: string, rows: Record<string, unknown>[], options: PdfOptions = {}) {
  if (!rows.length) return false;
  const bytes = await buildPdf(filename, rows, options);
  const url = URL.createObjectURL(new Blob([bytes as BlobPart], { type: "application/pdf" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return true;
}
