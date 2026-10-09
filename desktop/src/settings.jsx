import React, { useEffect, useState } from "react";
import { api } from "./api";

export function Settings({ onClose, report }) {
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
  }, []);
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
    <aside className="settings" aria-label="Réglages">
      <header>
        <h2>Réglages</h2>
        <button onClick={onClose}>Fermer</button>
      </header>
      <p>Configure le modèle et ses capacités. Les réglages sont conservés localement.</p>
      <h3>Conversation</h3>
      <label className="setting-field">
        Modèle
        <input
          value={typeof parsed?.model === "string" ? parsed.model : ""}
          disabled={!parsed}
          onChange={(event) => change("model", event.target.value)}
          spellCheck={false}
        />
      </label>
      <p>
        Choisis un modèle disponible sur ton compte backend. Les identifiants restent
        hors de l’interface.
      </p>
      <label className="setting-field">
        Instructions personnelles
        <textarea
          className="config instructions"
          value={typeof parsed?.instructions === "string" ? parsed.instructions : ""}
          disabled={!parsed}
          placeholder="Ta façon de travailler, le ton souhaité, tes préférences…"
          onChange={(event) => change("instructions", event.target.value || null)}
        />
      </label>
      <h3>Capacités</h3>
      <div className="plugins">
        {plugins.map((plugin) => (
          <div className="plugin-row" key={plugin.name}>
            {plugin.binding_available && <input
              type="checkbox"
              aria-label={`Activer ${plugin.name} pour l’agent`}
              checked={plugin.binding_enabled}
              disabled={plugin.binding_required || !plugin.running}
              onChange={() => toggle(plugin)}
            />}
            <span>{plugin.name}</span>
            <small>{plugin.binding_available
              ? (plugin.running ? "Chargé" : "Arrêté")
              : (plugin.running ? "Service actif" : "Service arrêté")}</small>
          </div>
        ))}
      </div>
      <details>
        <summary>Configuration avancée</summary>
        <p>
          Paramètres de l’agent et des plugins. Les services externes doivent être configurés séparément.
        </p>
        <label className="sr-only" htmlFor="config">
          Configuration de l’agent en JSON
        </label>
        <textarea
          id="config"
          className="config"
          value={config}
          onChange={(e) => setConfig(e.target.value)}
          spellCheck={false}
        />
      </details>
      <button
        className="primary"
        disabled={saving || typeof parsed?.model !== "string" || !parsed.model.trim()}
        onClick={save}
      >
        {saving ? "Enregistrement…" : "Enregistrer"}
      </button>
    </aside>
  );
}
