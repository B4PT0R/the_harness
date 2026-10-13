import React, { useEffect, useState } from "react";
import { useLocale } from "../i18n";

export function FileEditorSettings({ api }) {
  const { t } = useLocale();
  const [editor, setEditor] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [localOnly, setLocalOnly] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    api("local-files/settings", { signal: controller.signal })
      .then((result) => setEditor(result.editor))
      .catch((failure) => {
        if (failure.name === "AbortError") return;
        if ([401, 403, 404].includes(failure.status)) setLocalOnly(true);
        else setError(failure.message);
      });
    return () => controller.abort();
  }, [api]);
  async function change(value) {
    setSaving(true);
    setError("");
    try {
      const result = await api("local-files/settings", { method: "PUT", body: { editor: value } });
      setEditor(result.editor);
    } catch (failure) { setError(failure.message); }
    finally { setSaving(false); }
  }
  return <div className="file-editor-settings">
    {localOnly ? <p className="setting-help">{t("localResourcesOnly")}</p> : <>
      <div className="setting-field">
      <label htmlFor="file-editor">{t("fileEditor")}</label>
      <select id="file-editor" value={editor || "system"} disabled={!editor || saving}
        onChange={(event) => change(event.target.value)}>
        <option value="system">{t("systemEditor")}</option>
        <option value="vscode">Visual Studio Code</option>
      </select>
      </div>
      <p className="setting-help">{t(saving ? "saving" : "fileEditorHelp")}</p>
    </>}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}
