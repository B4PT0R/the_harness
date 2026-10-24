import React from "react";
import { useLocale } from "../i18n";
import { IconButton } from "./Icons";

export function AppShell({ preview = false, indicators, connection, settingsOpen, onToggleSettings, onOpenBrowser, openingBrowser = false, brandIcon, settings, children }) {
  const { t } = useLocale();
  return <div className="app">
    <header className="topbar">
      <div className="topbar-left">
        <div className="brand">
          <span className="connection" data-state={connection} role="status" aria-label={t(connection)} title={t(connection)}>
            <img src={brandIcon} alt="" />
          </span>
          <strong>The Harness</strong>
          {preview && <span className="preview-badge">{t("previewReadOnly")}</span>}
        </div>
        <div className="technical-status">{indicators}</div>
      </div>
      <div className="topbar-actions">
        {onOpenBrowser && <IconButton icon="web" label={t("openBrowser")} disabled={preview || openingBrowser || connection !== "Connected"} aria-busy={openingBrowser} onClick={onOpenBrowser} />}
        <IconButton icon="settings" label={t("settings")} aria-expanded={settingsOpen} onClick={onToggleSettings} />
      </div>
    </header>
    <div className="workspace"><main hidden={settingsOpen}>{children}</main>{settings}</div>
  </div>;
}
