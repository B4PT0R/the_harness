import React, { useCallback, useEffect, useState } from "react";
import QRCode from "qrcode";
import { useLocale } from "../i18n";

export function DeviceSettings({ api, readOnly = false }) {
  const { t, locale } = useLocale();
  const [network, setNetwork] = useState(null);
  const [clients, setClients] = useState([]);
  const [pairing, setPairing] = useState(null);
  const [qr, setQr] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const refresh = useCallback(async (signal) => {
    const [state, remote] = await Promise.all([
      api("client-remote/network", { signal }), api("client-remote", { signal }),
    ]);
    setNetwork(state);
    setClients(remote.clients || []);
  }, [api]);
  useEffect(() => {
    const controller = new AbortController();
    const update = () => refresh(controller.signal).catch(failure => {
      if (failure.name !== "AbortError") setError(failure.message);
    });
    update();
    const timer = setInterval(update, 10000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [refresh]);
  useEffect(() => {
    setQr("");
    setCopied(false);
    if (!pairing) return;
    let active = true;
    QRCode.toDataURL(pairing.pairing_uri, { width: 280, margin: 2, errorCorrectionLevel: "M" })
      .then(value => { if (active) setQr(value); }).catch(failure => setError(failure.message));
    const expiry = setTimeout(() => setPairing(null), Math.max(0, Date.parse(pairing.expires_at) - Date.now()));
    return () => { active = false; clearTimeout(expiry); };
  }, [pairing]);
  async function action(work) {
    setBusy(true); setError("");
    try { await work(); await refresh(); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function toggle() {
    const enabled = !network.enabled;
    if (enabled && !window.confirm(t("remoteEnableConfirm"))) return;
    await action(async () => {
      setNetwork(await api("client-remote/network", { method: "PUT", body: { enabled } }));
      setPairing(null);
    });
  }
  return <div className="device-settings">
    <p className="setting-help">{t("remoteHelp")}</p>
    <div className="remote-status" role="status">
      <strong>{t(network?.enabled ? "remoteEnabled" : "remoteDisabled")}</strong>
      {network?.endpoint && <code>{network.endpoint}</code>}
      {network?.error && <p className="setting-help">{network.error}</p>}
      {!network && !error && <p>{t("loading")}</p>}
    </div>
    <div className="remote-actions">
      <button type="button" disabled={readOnly || busy || !network || (!network.enabled && !network.available)} onClick={toggle}>
        {t(network?.enabled ? "remoteDisable" : "remoteEnable")}
      </button>
      <button type="button" disabled={busy} onClick={() => action(refresh)}>{t("remoteRefresh")}</button>
    </div>
    <p className="setting-help">{t("remoteDisableHelp")}</p>
    <h3>{t("remotePair")}</h3>
    <p className="setting-help">{t("remotePairHelp")}</p>
    <button type="button" disabled={readOnly || busy || !network?.enabled}
      onClick={() => action(async () => setPairing(await api("client-remote/pairings", { method: "POST", body: { endpoint: network.endpoint } })))}>
      {t("remoteCreatePairing")}
    </button>
    {pairing && <div className="remote-pairing">
      {qr && <img src={qr} width="280" height="280" alt={t("remoteQrAlt")} />}
      <p>{t("remoteExpires", { time: new Date(pairing.expires_at).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }) })}</p>
      <label className="setting-field">{t("remotePairLink")}
        <textarea readOnly rows="3" value={pairing.pairing_uri} spellCheck={false} onFocus={event => event.target.select()} />
      </label>
      <button type="button" onClick={async () => {
        try { await navigator.clipboard.writeText(pairing.pairing_uri); setCopied(true); }
        catch (failure) { setError(failure.message); }
      }}>{t(copied ? "remoteCopied" : "remoteCopy")}</button>
    </div>}
    <h3>{t("remoteClients")}</h3>
    {!clients.length && <p className="setting-help">{t("remoteNoClients")}</p>}
    <ul className="remote-clients">{clients.map(client => <li key={client.id}>
      <div><strong>{client.device_name || client.name || client.id}</strong><small>{client.platform}</small></div>
      <button type="button" disabled={readOnly || busy} onClick={() => {
        if (window.confirm(t("remoteRevokeConfirm"))) action(() => api(`client-remote/clients/${encodeURIComponent(client.id)}`, { method: "DELETE" }));
      }}>{t("remoteRevoke")}</button>
    </li>)}</ul>
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}

export function MobileSettings({ onClose }) {
  const { t, locale, setLocale } = useLocale();
  return <section className="settings mobile-settings" aria-label={t("settings")}>
    <header className="settings-header"><h1>{t("settings")}</h1><button autoFocus type="button" onClick={onClose}>{t("backToConversation")}</button></header>
    <div className="settings-content-inner"><label className="setting-field">{t("language")}
      <select value={locale} onChange={event => setLocale(event.target.value)}><option value="fr">Français</option><option value="en">English</option></select>
    </label><p className="setting-help">{t("remoteMobileHelp")}</p><code>{location.origin}</code></div>
  </section>;
}
