import React, { useEffect, useState } from "react";
import { useLocale } from "../i18n";
import { languages } from "../locales";
import { IconButton } from "./Icons";

export function Settings({ api, onClose, report }) {
  const { locale, setLocale, t } = useLocale();
  const [config, setConfig] = useState("");
  const [plugins, setPlugins] = useState([]);
  const [saving, setSaving] = useState(false);
  let parsed;
  try {
    parsed = JSON.parse(config);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) parsed = null;
  } catch {
    parsed = null;
  }
  function pluginLabel(name) {
    const key = `plugin_${name}`;
    const label = t(key);
    return label === key ? name : label;
  }
  function change(key, value) {
    setConfig(JSON.stringify({ ...parsed, [key]: value }, null, 2));
  }
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api("config", { signal: controller.signal }),
      api("plugins", { signal: controller.signal }),
    ])
      .then(([settings, installed]) => {
        setConfig(JSON.stringify(settings.config, null, 2));
        setPlugins(installed.plugins);
      })
      .catch((error) => {
        if (error.name !== "AbortError") report(error.message);
      });
    return () => controller.abort();
  }, [api, report]);
  async function save() {
    setSaving(true);
    try {
      await api("config", { method: "PATCH", body: JSON.parse(config) });
      onClose();
    } catch (error) {
      report(error.message);
    } finally {
      setSaving(false);
    }
  }
  async function toggle(plugin) {
    try {
      await api(`plugins/${plugin.name}/binding`, {
        method: "PUT",
        body: { enabled: !plugin.binding_enabled },
      });
      setPlugins((await api("plugins")).plugins);
    } catch (error) {
      report(error.message);
    }
  }
  return (
    <aside className="settings" aria-label={t("settings")}>
      <header>
        <h2>{t("settings")}</h2>
        <IconButton icon="close" label={t("close")} onClick={onClose} />
      </header>
      <div className="setting-field">
        <label htmlFor="ui-language">{t("language")}</label>
        <select id="ui-language" value={locale} onChange={(event) => setLocale(event.target.value)}>
          {Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
        </select>
      </div>
      <h3>{t("conversation")}</h3>
      <label className="setting-field">
        {t("model")}
        <input
          value={typeof parsed?.model === "string" ? parsed.model : ""}
          disabled={!parsed}
          onChange={(event) => change("model", event.target.value)}
          spellCheck={false}
        />
      </label>
      <label className="setting-field">
        {t("personalInstructions")}
        <textarea
          className="config instructions"
          value={typeof parsed?.instructions === "string" ? parsed.instructions : ""}
          disabled={!parsed}
          placeholder={t("optional")}
          onChange={(event) => change("instructions", event.target.value || null)}
        />
      </label>
      <h3>{t("capabilities")}</h3>
      <div className="plugins">
        {plugins.map((plugin) => (
          <div className="plugin-row" key={plugin.name}>
            {plugin.binding_available && <input
              type="checkbox"
              aria-label={t("enablePlugin", { name: pluginLabel(plugin.name) })}
              checked={plugin.binding_enabled}
              disabled={plugin.binding_required || !plugin.running}
              onChange={() => toggle(plugin)}
            />}
            <span>{pluginLabel(plugin.name)}</span>
            <small>{plugin.binding_available
              ? t(plugin.running ? "loaded" : "stopped")
              : t(plugin.running ? "serviceActive" : "serviceStopped")}</small>
          </div>
        ))}
      </div>
      <details>
        <summary>{t("advancedConfig")}</summary>
        <label className="sr-only" htmlFor="config">
          {t("configJson")}
        </label>
        <textarea
          id="config"
          className="config"
          value={config}
          onChange={(e) => setConfig(e.target.value)}
          spellCheck={false}
        />
      </details>
      <div className="save"><IconButton
        icon="save" label={t(saving ? "saving" : "save")}
        className="primary"
        disabled={saving || typeof parsed?.model !== "string" || !parsed.model.trim()}
        onClick={save}
      /></div>
    </aside>
  );
}
