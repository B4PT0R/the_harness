import React from "react";
import { useLocale } from "../i18n";
import { contextPercent } from "../context.js";

export function ContextGauge({ context, disabled, onCompact }) {
  const { t } = useLocale();
  const percent = contextPercent(context.ratio);
  const active = ["queued", "running"].includes(context.phase);
  const label = active ? t(context.phase === "queued" ? "compactionQueued" : "compacting")
    : percent === null ? t("contextUnknown") : t("contextUsage", { percent,
      tokens: context.tokens.toLocaleString(), limit: context.limit.toLocaleString() });
  return <button type="button" className={`icon-button context-gauge${active ? " is-compacting" : ""}${context.ratio >= 0.9 ? " is-full" : ""}`}
    disabled={disabled || active || percent === null} onClick={onCompact}
    aria-label={active ? label : `${label}. ${t("compactContext")}`} title={active ? label : `${label}\n${t("compactContext")}`} aria-busy={active}>
    <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <circle className="context-gauge-track" cx="16" cy="16" r="12" />
      <circle className="context-gauge-fill" cx="16" cy="16" r="12" pathLength="100"
        strokeDasharray={`${active ? 28 : percent ?? 0} 100`} transform="rotate(-90 16 16)" />
      {!active && <text x="16" y="16" dy=".35em" textAnchor="middle">{percent ?? "–"}</text>}
    </svg>
  </button>;
}
