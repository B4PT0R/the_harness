import React, { useState } from "react";
import { useLocale } from "../i18n";
import { Markdown } from "./Markdown";
import { cellText, chartScale, downloadText, tableCSV, tableView } from "../artifact-data";

function ExportButton({ content, filename, mime, label }) {
  const { t } = useLocale();
  return <button type="button" onClick={() => downloadText(content, filename, mime)}>{label || t("artifactExport")}</button>;
}

function Note({ payload }) {
  return payload.description && <p className="artifact-description">{payload.description}</p>;
}

export function MarkdownArtifact({ payload }) {
  return <>
    <div className="artifact-actions"><ExportButton content={payload.content} filename="document.md" mime="text/markdown;charset=utf-8" /></div>
    <div className="artifact-document" tabIndex={0}><Markdown>{payload.content}</Markdown></div>
    <Note payload={payload} />
  </>;
}

export function CodeArtifact({ payload }) {
  const { t } = useLocale();
  const [status, setStatus] = useState("");
  async function copy() {
    try { await navigator.clipboard.writeText(payload.content); setStatus(t("artifactCopied")); }
    catch { setStatus(t("artifactCopyFailed")); }
  }
  return <>
    <div className="artifact-actions">
      <span className="artifact-code-label">{payload.filename} · {payload.language}</span>
      <button type="button" onClick={copy}>{t("artifactCopy")}</button>
      <ExportButton content={payload.content} filename={payload.filename} />
      <span role="status">{status}</span>
    </div>
    <pre className="artifact-code-content" tabIndex={0}><code>{payload.content}</code></pre>
    <Note payload={payload} />
  </>;
}

export function TableArtifact({ payload }) {
  const { t } = useLocale();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState(null);
  const [page, setPage] = useState(0);
  const rows = tableView(payload.rows, query, sort);
  const last = Math.max(0, Math.ceil(rows.length / 50) - 1);
  const current = Math.min(page, last);
  return <>
    <div className="artifact-actions">
      <input type="search" aria-label={t("artifactFilter")} placeholder={t("artifactFilter")} value={query}
        onChange={event => { setQuery(event.target.value); setPage(0); }} />
      <ExportButton content={tableCSV(payload.columns, rows)} filename="table.csv" mime="text/csv;charset=utf-8" label={t("artifactCSV")} />
      <span role="status">{t("artifactRows", { count: rows.length, total: payload.rows.length })}</span>
    </div>
    <div className="artifact-table-scroll" tabIndex={0} role="region" aria-label={payload.title || t("artifactTable")}>
      <table className="artifact-table">
        <thead><tr>{payload.columns.map((column, index) => <th key={index} scope="col"
          aria-sort={sort?.column === index ? (sort.descending ? "descending" : "ascending") : "none"}>
          <button type="button" onClick={() => { setSort({ column: index, descending: sort?.column === index && !sort.descending }); setPage(0); }}>
            {column}{sort?.column === index ? (sort.descending ? " ↓" : " ↑") : " ↕"}
          </button>
        </th>)}</tr></thead>
        <tbody>{rows.slice(current * 50, (current + 1) * 50).map((row, index) => <tr key={index}>
          {row.map((cell, column) => <td key={column}>{cellText(cell)}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
    {rows.length === 0 && <p role="status">{t("artifactNoRows")}</p>}
    {last > 0 && <nav className="artifact-actions" aria-label={t("artifactPages")}>
      <button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>{t("artifactPrevious")}</button>
      <span>{current + 1} / {last + 1}</span>
      <button type="button" disabled={current === last} onClick={() => setPage(current + 1)}>{t("artifactNext")}</button>
    </nav>}
    <Note payload={payload} />
  </>;
}

export function ChartArtifact({ payload }) {
  const { t, locale } = useLocale();
  const { labels, series } = payload;
  const { y, ticks } = chartScale(series);
  const compact = labels.length <= 6 && series.length <= 3;
  const width = payload.chart_type === "bar" ? Math.max(360, labels.length * series.length * 14 + 100) : (compact ? 360 : 700);
  const step = (width - 100) / labels.length;
  const x = index => 75 + (index + 0.5) * step;
  const format = number => new Intl.NumberFormat(locale, { maximumSignificantDigits: 4, notation: Math.abs(number) >= 1e6 ? "compact" : "standard" }).format(number);
  const table = { columns: [t("artifactCategory"), ...series.map(item => item.name)], rows: labels.map((label, i) => [label, ...series.map(item => item.values[i])]) };
  return <>
    <div className="artifact-chart-scroll" tabIndex={0} role="region" aria-label={payload.title || t("artifactChart")}>
      <svg viewBox={`0 0 ${width} 275`} style={{ minWidth: compact ? 0 : width }} role="img" aria-label={payload.title || t("artifactChart")}>
        <title>{payload.title || t("artifactChart")}</title>
        <desc>{t("artifactChartDescription")}</desc>
        {ticks.map((tick, i) => <g key={i}>
          <line className="artifact-grid" x1="75" x2={width - 25} y1={y(tick)} y2={y(tick)} />
          <text x="65" y={y(tick) + 4} textAnchor="end">{format(tick)}</text>
        </g>)}
        <line className="artifact-zero" x1="75" x2={width - 25} y1={y(0)} y2={y(0)} />
        {series.map((item, s) => <g key={s} className={`artifact-series artifact-series-${s}`}>
          {payload.chart_type === "line"
            ? <><polyline fill="none" stroke="currentColor" strokeWidth="2.5" points={item.values.map((value, i) => `${x(i)},${y(value)}`).join(" ")} />
                {item.values.map((value, i) => <circle key={i} cx={x(i)} cy={y(value)} r="3" fill="currentColor"><title>{labels[i]} · {item.name}: {value} {payload.unit}</title></circle>)}</>
            : item.values.map((value, i) => <rect key={i} x={x(i) - step * .4 + s * step * .8 / series.length} y={Math.min(y(value), y(0))}
                width={step * .75 / series.length} height={Math.max(1, Math.abs(y(value) - y(0)))} fill="currentColor">
                <title>{labels[i]} · {item.name}: {value} {payload.unit}</title>
              </rect>)}
        </g>)}
        {labels.map((label, i) => (i % Math.ceil(labels.length / 8) === 0 || i === labels.length - 1) &&
          <text key={i} x={x(i)} y="245" textAnchor="middle"><title>{label}</title>{label.length > 16 ? `${label.slice(0, 15)}…` : label}</text>)}
      </svg>
    </div>
    <ul className="artifact-legend">{series.map((item, i) => <li key={i}><span className={`artifact-series artifact-series-${i}`} aria-hidden="true">●</span> {item.name}</li>)}</ul>
    {payload.unit && <p className="artifact-description">{payload.unit}</p>}
    <details className="artifact-chart-data"><summary>{t("artifactChartData")}</summary><TableArtifact payload={table} /></details>
    <Note payload={payload} />
  </>;
}

export function TimelineArtifact({ payload }) {
  return <>
    <ol className="artifact-timeline-list">{payload.entries.map((entry, index) => <li key={index}>
      <span className="artifact-timeline-label">{entry.label}</span>
      <div><strong>{entry.title}</strong>{entry.detail && <p>{entry.detail}</p>}</div>
    </li>)}</ol>
    <Note payload={payload} />
  </>;
}
