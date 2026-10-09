import React, { useEffect, useRef, useState } from "react";
import { useLocale } from "../i18n";
import { Icon } from "./Icons";

export function DangerZone({ api, disabled = false }) {
  const { t } = useLocale();
  const dialog = useRef(null);
  const pending = useRef(false);
  const [target, setTarget] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (target) dialog.current.showModal();
  }, [target]);
  function dismiss() {
    if (pending.current) return;
    dialog.current.close();
    setTarget(null);
    setError("");
  }
  async function reset() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await api(target, { method: "DELETE" });
      dialog.current.close();
      setTarget(null);
      setDone(true);
    } catch (failure) {
      setError(failure.message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="danger-zone" aria-labelledby="danger-zone-title">
      <h3 id="danger-zone-title">{t("dangerZone")}</h3>
      <div className="danger-actions">
        {["session", "memory"].map((kind) => <button
          key={kind} type="button" className="danger-button" disabled={disabled || busy}
          onClick={() => { setDone(false); setTarget(kind); }}
        ><Icon name="reset" />{t(kind === "session" ? "resetSession" : "resetMemory")}</button>)}
      </div>
      {done && <p className="reset-status" role="status">{t("resetDone")}</p>}
      <dialog ref={dialog} className="reset-dialog" aria-labelledby="reset-title" aria-describedby="reset-description"
        onCancel={(event) => { event.preventDefault(); dismiss(); }}>
        <h2 id="reset-title">{t(target === "session" ? "resetSession" : "resetMemory")}</h2>
        <p id="reset-description">{t(target === "session" ? "resetSessionWarning" : "resetMemoryWarning")}</p>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="reset-dialog-actions">
          <button type="button" autoFocus disabled={busy} onClick={dismiss}>{t("cancel")}</button>
          <button type="button" className="danger-button" disabled={busy} onClick={reset}>
            {t(busy ? "resetting" : "confirmReset")}
          </button>
        </div>
      </dialog>
    </section>
  );
}
