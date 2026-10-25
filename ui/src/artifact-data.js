// Pure helpers shared by artifact renderers and their tests.
export const cellText = value => value == null ? "" : String(value);

export function tableCSV(columns, rows) {
  const quote = value => {
    let text = cellText(value);
    // Spreadsheet formulas are data, never an accidental execution on opening CSV.
    if (typeof value === "string" && /^[\s]*[=+\-@\t\r]/u.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  };
  return "\uFEFF" + [columns, ...rows].map(row => row.map(quote).join(",")).join("\r\n");
}

export function tableView(rows, query = "", sort = null) {
  const needle = query.toLocaleLowerCase();
  const filtered = rows.filter(row => !needle || row.some(value => cellText(value).toLocaleLowerCase().includes(needle)));
  if (!sort) return filtered;
  return filtered.toSorted((a, b) => {
    const left = a[sort.column], right = b[sort.column];
    const order = typeof left === "number" && typeof right === "number"
      ? left - right : cellText(left).localeCompare(cellText(right), undefined, { numeric: true });
    return sort.descending ? -order : order;
  });
}

export function downloadText(content, name, mime = "text/plain;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = String(name || "artifact.txt").split(/[\\/]/).pop() || "artifact.txt";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function chartScale(series) {
  const values = series.flatMap(item => item.values);
  const magnitude = Math.max(...values.map(Math.abs)) || 1;
  const min = Math.min(0, ...values.map(value => value / magnitude));
  const max = Math.max(0, ...values.map(value => value / magnitude)) || (min === 0 ? 1 : 0);
  const span = max - min;
  return {
    y: value => 220 - ((value / magnitude - min) / span) * 200,
    ticks: Array.from({ length: 5 }, (_, i) => (min + span * i / 4) * magnitude),
  };
}
