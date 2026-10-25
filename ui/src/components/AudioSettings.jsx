import React, { useEffect, useState } from "react";
import { useLocale } from "../i18n";
import { getTtsVolume, setTtsVolume, subscribeTtsVolume } from "../audio-preferences.js";

export function AudioSettings({ readOnly = false }) {
  const { t } = useLocale();
  const [volume, setVolume] = useState(getTtsVolume);
  useEffect(() => subscribeTtsVolume(setVolume), []);
  const percent = Math.round(volume * 100);
  return <>
    <div className="setting-field">
      <label htmlFor="tts-autoplay-volume">{t("ttsAutoplayVolume")}</label>
      <div className="audio-volume">
        <input id="tts-autoplay-volume" type="range" min="0" max="100" step="1"
          value={percent} disabled={readOnly} aria-describedby="tts-volume-help"
          aria-valuetext={`${percent} %`} onChange={(event) => setTtsVolume(Number(event.target.value) / 100)} />
        <output htmlFor="tts-autoplay-volume">{percent} %</output>
      </div>
    </div>
    <p id="tts-volume-help" className="setting-help">{t("ttsAutoplayVolumeHelp")}</p>
  </>;
}
