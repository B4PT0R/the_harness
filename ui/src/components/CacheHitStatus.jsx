import React from "react";
import { useLocale } from "../i18n";
import { GaugeRing } from "./GaugeRing";

export function CacheHitStatus({ stats }) {
  const { t, locale } = useLocale();
  const format = (value) => Number.isFinite(value)
    ? value.toLocaleString(locale, { maximumFractionDigits: 1 }) : "–";
  const known = Number.isFinite(stats?.ema_percent);
  const label = t("cacheHitLabel", { percent: format(stats?.ema_percent) });
  const detail = known ? t("cacheHitDetail", {
    alpha: format(stats.alpha), samples: stats.samples,
    last: format(stats.last_percent), unreported: stats.unreported,
    updated: new Date(stats.updated_at * 1000).toLocaleString(locale),
  }) : t("cacheHitUnknown");
  return <span className="technical-gauge cache-hit" role="img" title={detail} aria-label={`${label}. ${detail}`}>
    <GaugeRing value={known ? stats.ema_percent : null} />
    <span className="gauge-caption" aria-hidden="true">CH</span>
  </span>;
}
