import React, { useEffect, useRef, useState } from "react";
import { useLocale } from "../i18n";
import { IconButton } from "./Icons";

export function QuotaGauge({ quota, readOnly = false }) {
  const { t, locale } = useLocale();
  const dialog = useRef(null);
  const [confirm, setConfirm] = useState(null);
  const [error, setError] = useState(false);
  const data = quota.data;
  const raw = data?.quota_7d?.used_percent;
  const percent = typeof raw === "number" ? Math.round(Math.min(100, Math.max(0, raw))) : null;
  const unavailable = quota.failed || data?.error;
  const label = !data && !quota.failed ? t("quotaLoading")
    : unavailable || percent === null ? t("quotaUnavailable") : t("quotaUsage", { percent });
  const formatDate = (value) => value && Number.isFinite(new Date(value).getTime())
    ? new Date(value).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" }) : t("quotaNoExpiry");
  const credits = (data?.credits || []).filter((credit) => credit.status === "available"
    && credit.reset_type === "codex_rate_limits" && (!credit.expires_at || new Date(credit.expires_at).getTime() > Date.now()))
    .sort((a, b) => (new Date(a.expires_at || "9999-01-01") - new Date(b.expires_at || "9999-01-01")));
  const operations = Object.entries(data?.operations || {}).sort((a, b) => b[1].started_at - a[1].started_at);
  const uncertain = operations.some(([, operation]) => ["pending", "unknown"].includes(operation.status));
  useEffect(() => () => dialog.current?.close(), []);
  function close() { dialog.current.close(); setConfirm(null); setError(false); }
  async function consume() {
    setError(false);
    try {
      const result = await quota.consume(confirm.id);
      if (result) { setConfirm(null); if (result.operation?.status !== "confirmed") setError(true); }
    } catch { setError(true); await quota.refresh(); }
  }
  return <>
    <button type="button" className={`quota-gauge${data?.exhausted ? " is-full" : ""}`}
      aria-haspopup="dialog" aria-label={`${label}. ${t("quotaOpen")}`} title={`${label}\n${t("quotaOpen")}`}
      onClick={() => { dialog.current.showModal(); quota.refresh(); }}>
      <span className="quota-gauge-caption" aria-hidden="true">7{locale === "fr" ? "j" : "d"}</span>
      <span aria-hidden="true">{unavailable || percent === null ? "–" : `${percent}%`}</span>
      <span className="quota-gauge-track" aria-hidden="true"><span style={{ width: `${percent ?? 0}%` }} /></span>
    </button>
    <dialog ref={dialog} className="reset-dialog quota-dialog" aria-labelledby="quota-title"
      onCancel={() => { setConfirm(null); setError(false); }}>
      <header className="quota-dialog-header"><h2 id="quota-title">{t("quotaTitle")}</h2>
        <IconButton icon="close" label={t("close")} onClick={close} /></header>
      <p role="status">{label}</p>
      {data?.quota_7d?.reset_at && <p className="setting-help">{t("quotaRenews", { time: formatDate(data.quota_7d.reset_at * 1000) })}</p>}
      {data?.exhausted && <p className="quota-hold">{t("quotaHeld")}</p>}
      <h3>{t("quotaResets")}</h3>
      {!data ? <p>{t(quota.failed ? "quotaUnavailable" : "quotaLoading")}</p> : !credits.length ? <p>{t("quotaNoResets")}</p> : <ul className="quota-credits">
        {credits.map((credit, index) => <li key={credit.id}>
          <div><strong>{t("quotaReset", { number: index + 1 })}</strong>
            <small>{t("quotaExpires", { time: formatDate(credit.expires_at) })}</small></div>
          <button type="button" disabled={readOnly || quota.pending || Boolean(unavailable) || uncertain || Boolean(data.operations?.[credit.id])}
            onClick={() => { setConfirm(credit); setError(false); }}>{t("quotaUse")}</button>
        </li>)}
      </ul>}
      {confirm && <div className="quota-confirm">
        <p>{t("quotaConfirm", { time: formatDate(confirm.expires_at) })}</p>
        <div className="reset-dialog-actions">
          <button type="button" disabled={quota.pending} onClick={() => setConfirm(null)}>{t("cancel")}</button>
          <button type="button" className="primary" disabled={readOnly || quota.pending} onClick={consume}>{t(quota.pending ? "saving" : "quotaConfirmUse")}</button>
        </div>
      </div>}
      {error && <p className="error" role="alert">{t("quotaConsumeFailed")}</p>}
      {!!operations.length && <details className="quota-receipts"><summary>{t("quotaReceipts")}</summary>
        <ul>{operations.slice(0, 10).map(([id, operation]) => <li key={id}>
          {formatDate(operation.started_at * 1000)} · {t(`quotaReason_${operation.reason}`)} · {t(`quotaResult_${operation.status}`)}
        </li>)}</ul>
      </details>}
      {uncertain && <p className="error" role="status">{t("quotaUncertain")}</p>}
      <p className="setting-help">{t("quotaExpiryHelp")}</p>
      <button type="button" disabled={quota.pending} onClick={() => quota.refresh()}>{t("remoteRefresh")}</button>
    </dialog>
  </>;
}
