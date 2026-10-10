import React, { useEffect, useRef, useState } from "react";
import { useLocale } from "../i18n";

export function SurfaceSettings({ api, active }) {
  const { t } = useLocale();
  const [surfaces, setSurfaces] = useState(null);
  const [busy, setBusy] = useState(null);
  const [confirmation, setConfirmation] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [cancelling, setCancelling] = useState(null);
  const pending = useRef(null);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    api("surfaces", { signal: controller.signal })
      .then((data) => setSurfaces(data.surfaces))
      .catch((failure) => { if (failure.name !== "AbortError") setError(failure.message); });
    return () => controller.abort();
  }, [api, active]);

  async function run(name, action, release) {
    if (pending.current) return;
    const operation = { name, action, cancelled: false };
    pending.current = operation;
    setBusy(operation);
    setConfirmation(null);
    setError("");
    setNotice("");
    try {
      if (action !== "refresh") {
        await api(`surfaces/${encodeURIComponent(name)}/${action}`, {
          method: "POST", ...(release ? { body: { release } } : {}),
        });
      }
      setSurfaces((await api("surfaces")).surfaces);
      if (action !== "refresh") setNotice(t(operation.cancelled ? "buildCancelled" : `${action}Done`));
    } catch (failure) {
      if (operation.cancellation) await operation.cancellation.catch(() => {});
      if (operation.cancelled) setNotice(t("buildCancelled"));
      else setError(failure.message);
    } finally {
      pending.current = null;
      setBusy(null);
      setCancelling(null);
    }
  }

  async function cancelBuild(name) {
    if (cancelling) return;
    const operation = pending.current;
    setCancelling(name);
    const request = api(`surfaces/${encodeURIComponent(name)}/cancel`, { method: "POST" });
    if (operation) operation.cancellation = request;
    try {
      const result = await request;
      if (operation) operation.cancelled = result.cancelled;
      else {
        setSurfaces((await api("surfaces")).surfaces);
        if (result.cancelled) setNotice(t("buildCancelled"));
      }
    } catch (failure) {
      setError(failure.message);
    } finally {
      setCancelling(null);
    }
  }

  return <div className="surface-settings">
      <p className="setting-help">{t("surfaceHelp")}</p>
      <button type="button" disabled={!!busy} onClick={() => run(null, "refresh")}>{t("refresh")}</button>
      {surfaces === null && !error && <p role="status">{t("loading")}</p>}
      {surfaces?.length === 0 && <p>{t("noSurfaces")}</p>}
      {surfaces?.map((surface) => {
        const candidate = surface.candidate && surface.candidate !== surface.active;
        const preview = surface.preview_route?.startsWith("/") && !surface.preview_route.startsWith("//")
          ? `${surface.preview_route}/${encodeURIComponent(surface.candidate)}/` : null;
        const confirming = confirmation?.name === surface.name;
        return <section className="surface-card" key={surface.name} aria-label={surface.name}>
          <strong>{surface.name}</strong>
          <dl>
            {["active", "candidate", "previous"].map((key) => <React.Fragment key={key}>
              <dt>{t(`release_${key}`)}</dt>
              <dd><code title={surface[key] || undefined}>{surface[key]?.slice(0, 12) || t("none")}</code></dd>
            </React.Fragment>)}
          </dl>
          <div className="surface-actions">
            <button type="button" disabled={!!busy || !!surface.building} onClick={() => run(surface.name, "build")}>{t("buildPreview")}</button>
            {candidate && preview && <a href={preview} target="_blank" rel="noopener noreferrer">{t("openPreview")}</a>}
            <button type="button" disabled={!!busy || !candidate} onClick={() => setConfirmation({ name: surface.name, action: "publish", release: surface.candidate })}>{t("publish")}</button>
            <button type="button" disabled={!!busy || !surface.previous} onClick={() => setConfirmation({ name: surface.name, action: "rollback" })}>{t("rollback")}</button>
          </div>
          {surface.building && busy?.name !== surface.name && <div className="surface-actions" role="status">
            <span>{t("buildingPreview")}</span>
            <button type="button" disabled={!!cancelling} onClick={() => cancelBuild(surface.name)}>{t("cancelBuild")}</button>
          </div>}
          {confirming && <div className="surface-confirmation">
            <p>{t(confirmation.action === "publish" ? "publishWarning" : "rollbackWarning")}</p>
            <div className="surface-actions">
              <button type="button" disabled={!!busy} onClick={() => setConfirmation(null)}>{t("cancel")}</button>
              <button type="button" className="primary" disabled={!!busy} onClick={() => run(confirmation.name, confirmation.action, confirmation.release)}>{t("confirm")}</button>
            </div>
          </div>}
        </section>;
      })}
      {busy && <div className="surface-actions" role="status">
        <span>{t(busy.action === "build" ? "buildingPreview" : "saving")}</span>
        {busy.action === "build" && <button type="button" disabled={!!cancelling} onClick={() => cancelBuild(busy.name)}>{t("cancelBuild")}</button>}
      </div>}
      {notice && <p className="setting-help" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}
  </div>;
}
