export function downloadCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return false;
  const headers = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const escape = (value: unknown) =>
    `"${String(value ?? "").replaceAll('"', '""')}"`;
  const contents = [
    headers.map(escape).join(","),
    ...rows.map((row) =>
      headers.map((header) => escape(row[header])).join(","),
    ),
  ].join("\r\n");
  const url = URL.createObjectURL(
    new Blob([contents], { type: "text/csv;charset=utf-8" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.click();
  URL.revokeObjectURL(url);
  return true;
}
