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

export function downloadBrandedCsv(
  filename: string,
  title: string,
  subtitle: string,
  logoPath: string,
  columns: { key: string; label: string }[],
  rows: Record<string, unknown>[],
) {
  if (!rows.length) return false;
  const escape = (value: unknown) => {
    let text = String(value ?? "");
    if (/^[=+@\-\t\r]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  };
  const contents = [
    ["CHRISLAND UNIVERSITY"].map(escape).join(","),
    ["CHAPEL ATTENDANCE REPORT"].map(escape).join(","),
    [title].map(escape).join(","),
    [subtitle].map(escape).join(","),
    ["University logo", logoPath].map(escape).join(","),
    [],
    columns.map((column) => escape(column.label)).join(","),
    ...rows.map((row) => columns.map(({ key }) => escape(row[key])).join(",")),
  ].join("\r\n");
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", contents], { type: "text/csv;charset=utf-8" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.click();
  URL.revokeObjectURL(url);
  return true;
}
