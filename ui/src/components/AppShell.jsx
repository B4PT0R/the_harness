import React from "react";
import { useLocale } from "../i18n";
import { IconButton } from "./Icons";

export function AppShell({ preview = false, connection, settingsOpen, onToggleSettings, brandIcon, settings, children }) {
  const { t } = useLocale();
  return <div className="app">
    <header className="topbar">
      <div className="brand">
        <img src={brandIcon} alt="" />
        <strong>The Harness</strong>
        {preview && <span className="preview-badge">{t("previewReadOnly")}</span>}
        <span className="connection" data-state={connection} role="status" aria-label={t(connection)} title={t(connection)} />
      </div>
      <IconButton icon="settings" label={t("settings")} aria-expanded={settingsOpen} onClick={onToggleSettings} />
    </header>
    <div className="workspace"><main hidden={settingsOpen}>{children}</main>{settings}</div>
  </div>;
}
