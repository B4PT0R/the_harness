import React from "react";
import { useLocale } from "../i18n";
import { IconButton } from "./Icons";

export function AppShell({ connection, settingsOpen, onToggleSettings, brandIcon, settings, children }) {
  const { t } = useLocale();
  return <div className="app">
    <header className="topbar">
      <div className="brand">
        <img src={brandIcon} alt="" />
        <strong>The Harness</strong>
        <span className="connection" data-state={connection} role="status" aria-label={t(connection)} title={t(connection)} />
      </div>
      <IconButton icon="settings" label={t("settings")} aria-expanded={settingsOpen} onClick={onToggleSettings} />
    </header>
    <div className="workspace"><main>{children}</main>{settings}</div>
  </div>;
}
