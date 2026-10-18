import React from "react";
import { useLocale } from "../i18n";

// Common ChatGPT voice names, checked against OpenAI's Voice help on 2026-10-18.
// https://help.openai.com/en/articles/20001274-chatgpt-voice
// Preserve account/model-specific values configured through Advanced settings.
const voices = ["arbor", "breeze", "cove", "ember", "juniper", "maple", "sol", "spruce", "vale"];

export function VoiceSettings({ config, saving, onChange }) {
  const { t } = useLocale();
  const voice = config && typeof config === "object" && !Array.isArray(config) ? config : null;
  const disabled = !voice || saving;
  const selected = typeof voice?.voice === "string" ? voice.voice : "";
  function change(key, value) {
    onChange({ ...voice, [key]: value });
  }
  return <>
    <p className="setting-help">{t("voiceSettingsHelp")}</p>
    {!voice && <p className="setting-help" role="status">{t("voiceSettingsUnavailable")}</p>}
    <label className="setting-field">
      {t("voiceChoice")}
      <select value={selected} disabled={disabled} onChange={(event) => change("voice", event.target.value)}>
        {!voices.includes(selected) && <option value={selected}>{selected || t("loading")}</option>}
        {voices.map((name) => <option key={name} value={name}>
          {name[0].toUpperCase() + name.slice(1)}
        </option>)}
      </select>
    </label>
    <p className="setting-help">{t("voiceChoiceHelp")}</p>
    <label className="setting-field">
      {t("voiceModel")}
      <input value={typeof voice?.model === "string" ? voice.model : ""} disabled={disabled}
        onChange={(event) => change("model", event.target.value)} spellCheck={false} />
    </label>
    <p className="setting-help">{t("voiceModelHelp")}</p>
    <label className="setting-checkbox">
      <input type="checkbox" checked={voice?.delegation_ack_filler === true} disabled={disabled}
        onChange={(event) => change("delegation_ack_filler", event.target.checked)} />
      <span>{t("voiceWaitingReplies")}</span>
    </label>
    <p className="setting-help">{t("voiceWaitingRepliesHelp")}</p>
  </>;
}
