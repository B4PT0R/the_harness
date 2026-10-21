import React, { useState } from "react";
import { useLocale } from "../i18n";

export function QuotaSettings({ quota, readOnly = false }) {
  const { t } = useLocale();
  const [error, setError] = useState(false);
  async function change(value) {
    setError(false);
    try { await quota.policy(value); }
    catch { setError(true); }
  }
  return <div className="quota-settings">
    <div className="setting-field">
      <label htmlFor="quota-policy">{t("quotaPolicy")}</label>
      <select id="quota-policy" value={quota.data?.exhausted_policy || "block"}
        disabled={readOnly || !quota.data || quota.pending || quota.failed}
        onChange={(event) => change(event.target.value)}>
        <option value="block">{t("quotaBlock")}</option>
        <option value="consume_earliest">{t("quotaAutoReset")}</option>
      </select>
    </div>
    <p className="setting-help">{t("quotaPolicyHelp")}</p>
    <p className="setting-help">{t("quotaExpiryHelp")}</p>
    {error && <p className="error" role="alert">{t("quotaSaveFailed")}</p>}
  </div>;
}
