import React, { useEffect, useRef, useState } from "react";
import { useLocale } from "../i18n";
import { languages } from "../locales";
import { Icon } from "./Icons";
import { DangerZone } from "./DangerZone";
import { FileEditorSettings } from "./FileEditorSettings";
import { pluginStatusKey } from "../plugins";

export function Settings({ api, onClose }) {
  const { locale, setLocale, t } = useLocale();
  const [section, setSection] = useState("general");
  const [original, setOriginal] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const back = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;
  const [config, setConfig] = useState("");
  const [plugins, setPlugins] = useState([]);
  const [saving, setSaving] = useState(false);
  const [changingPlugin, setChangingPlugin] = useState(null);
  let parsed;
  try {
    parsed = JSON.parse(config);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) parsed = null;
  } catch {
    parsed = null;
  }
  useEffect(() => {
    const previous = document.activeElement;
    back.current?.focus();
    function escape(event) {
      if (event.key === "Escape" && !event.defaultPrevented && !document.querySelector("dialog[open]")) close.current();
    }
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("keydown", escape);
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  function pluginLabel(name) {
    const key = `plugin_${name}`;
    const label = t(key);
    return label === key ? name : label;
  }
  function change(key, value) {
    setNotice("");
    setConfig(JSON.stringify({ ...parsed, [key]: value }, null, 2));
  }
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api("config", { signal: controller.signal }),
      api("plugins", { signal: controller.signal }),
    ]).then(([settings, installed]) => {
      const value = JSON.stringify(settings.config, null, 2);
      setConfig(value);
      setOriginal(value);
      setPlugins(installed.plugins);
    }).catch((failure) => {
      if (failure.name !== "AbortError") setError(failure.message);
    });
    return () => controller.abort();
  }, [api]);
  async function save() {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      await api("config", { method: "PATCH", body: parsed });
      setOriginal(config);
      setNotice(t("settingsSaved"));
    } catch (failure) {
      setError(failure.message);
    } finally {
      setSaving(false);
    }
  }
  async function toggle(plugin) {
    setChangingPlugin(plugin.name);
    setError("");
    try {
      await api(`plugins/${plugin.name}/binding`, {
        method: "PUT", body: { enabled: !plugin.binding_enabled },
      });
      setPlugins((await api("plugins")).plugins);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setChangingPlugin(null);
    }
  }
  const sections = ["general", "conversation", "capabilities", "advanced", "data"];
  return (
    <section className="settings" aria-label={t("settings")}>
      <header className="settings-header">
        <h1>{t("settings")}</h1>
        <button type="button" className="settings-back" ref={back} onClick={onClose}>
          <Icon name="back" />{t("backToConversation")}
        </button>
      </header>
      <div className="settings-layout">
        <nav className="settings-nav" aria-label={t("settingsSections")}>
          {sections.map((name) => <button key={name} type="button"
            aria-current={section === name ? "page" : undefined}
            aria-controls={`settings-${name}`} onClick={() => setSection(name)}>
            {t(`settings_${name}`)}
          </button>)}
        </nav>
        <div className="settings-content">
          <div className="settings-content-inner">
            <h2>{t(`settings_${section}`)}</h2>
            <section id="settings-general" hidden={section !== "general"}>
              <div className="setting-field">
                <label htmlFor="ui-language">{t("language")}</label>
                <select id="ui-language" value={locale} onChange={(event) => setLocale(event.target.value)}>
                  {Object.entries(languages).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
                </select>
              </div>
              <p className="setting-help">{t("languageImmediate")}</p>
              <FileEditorSettings api={api} />
            </section>
            <section id="settings-conversation" hidden={section !== "conversation"}>
              <label className="setting-field">
                {t("model")}
                <input value={typeof parsed?.model === "string" ? parsed.model : ""}
                  disabled={!parsed || saving} onChange={(event) => change("model", event.target.value)} spellCheck={false} />
              </label>
              <label className="setting-field">
                {t("personalInstructions")}
                <textarea className="config instructions" value={typeof parsed?.instructions === "string" ? parsed.instructions : ""}
                  disabled={!parsed || saving} placeholder={t("optional")}
                  onChange={(event) => change("instructions", event.target.value || null)} />
              </label>
            </section>
            <section id="settings-capabilities" hidden={section !== "capabilities"}>
              <p className="setting-help">{t("capabilitiesHelp")}</p>
              <div className="plugins">
                {plugins.map((plugin) => <div className="plugin-row" key={plugin.name}>
                  {plugin.binding_available && <input type="checkbox"
                    aria-label={t("enablePlugin", { name: pluginLabel(plugin.name) })}
                    checked={plugin.binding_enabled}
                    disabled={plugin.binding_required || !plugin.running || changingPlugin !== null}
                    title={plugin.binding_required ? t("requiredPlugin") : undefined} onChange={() => toggle(plugin)} />}
                  <span>{pluginLabel(plugin.name)}</span>
                  <small>{t(changingPlugin === plugin.name ? "saving" : pluginStatusKey(plugin))}</small>
                </div>)}
              </div>
            </section>
            <section id="settings-advanced" hidden={section !== "advanced"}>
              <label className="setting-field" htmlFor="config">{t("configJson")}</label>
              <textarea id="config" className="config" value={config} disabled={saving}
                onChange={(event) => setConfig(event.target.value)} spellCheck={false} />
              {!parsed && config && <p className="error" role="alert">{t("invalidConfig")}</p>}
            </section>
            <section id="settings-data" hidden={section !== "data"}>
              <DangerZone api={api} disabled={saving || changingPlugin !== null} />
            </section>
          </div>
        </div>
      </div>
      <footer className="settings-footer">
        <div aria-live="polite">
          {error ? <p className="error" role="alert">{error}</p>
            : <p className="setting-help">{config !== original ? t("unsavedSettings") : notice}</p>}
        </div>
        <button type="button" className="primary settings-save"
          disabled={saving || config === original || typeof parsed?.model !== "string" || !parsed.model.trim()}
          onClick={save}><Icon name="save" />{t(saving ? "saving" : "save")}</button>
      </footer>
    </section>
  );
}
