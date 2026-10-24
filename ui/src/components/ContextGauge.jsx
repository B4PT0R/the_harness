import React from "react";
import { useLocale } from "../i18n";
import { GaugeRing } from "./GaugeRing";
import { contextPercent } from "../context.js";

export function ContextGauge({ context, disabled, onCompact }) {
  const { t } = useLocale();
  const percent = contextPercent(context.ratio);
  const active = ["queued", "running"].includes(context.phase);
  const label = active ? t(context.phase === "queued" ? "compactionQueued" : "compacting")
    : percent === null ? t("contextUnknown") : t("contextUsage", { percent,
      tokens: context.tokens.toLocaleString(), limit: context.limit.toLocaleString() });
  return <button type="button" className={`technical-gauge context-gauge${active ? " is-compacting" : ""}${context.ratio >= 0.9 ? " is-full" : ""}`}
    disabled={disabled || active || percent === null} onClick={onCompact}
    aria-label={active ? label : `${label}. ${t("compactContext")}`} title={active ? label : `${label}\n${t("compactContext")}`} aria-busy={active}>
    <GaugeRing value={percent} active={active} />
    <span className="gauge-caption" aria-hidden="true">CTX</span>
  </button>;
}
