import React, { useRef } from "react";
import { useLocale } from "../i18n";
import { IconButton } from "./Icons";
import { handleComposerKeyDown } from "../composer-keyboard.js";

export function Composer({ draft, onDraftChange, files, onFilesChange, sending, chatAvailable, voiceAvailable, voiceState, busy, connected, activity, error, onDismissError, onSubmit, onToggleVoice, onInterrupt }) {
  const { t } = useLocale();
  const fileInput = useRef(null);
  const canSubmit = !sending && chatAvailable === true && (Boolean(draft.trim()) || files.length > 0) && connected;
  const voiceLabel = voiceState === "idle" ? "voiceStart" : voiceState === "connecting" ? "cancel" : voiceState === "stopping" ? "voiceStopping" : "voiceEnd";
  return <div className="composer-area">
    {error && <div className="error" role="alert">{error}<IconButton icon="close" label={t("close")} onClick={onDismissError} /></div>}
    <div className="activity" role="status">{chatAvailable === false ? t("chatUnavailable") : busy ? activity || t("working") : ""}</div>
    <form className="composer" onSubmit={onSubmit}>
      {!!files.length && <div className="attachments">{files.map((file, index) => <button
        type="button" key={index} disabled={sending} aria-label={t("removeAttachment", { name: file.name })}
        onClick={() => onFilesChange(files.filter((_, i) => i !== index))}
      >{file.name} ×</button>)}</div>}
      <label className="sr-only" htmlFor="message">{t("message")}</label>
      <textarea id="message" placeholder={t("messagePlaceholder")} value={draft} onChange={(event) => onDraftChange(event.target.value)} onKeyDown={(event) => handleComposerKeyDown(event, canSubmit)} rows={3} disabled={sending || chatAvailable !== true} />
      <div className="composer-actions">
        <input ref={fileInput} type="file" multiple hidden onChange={(event) => { onFilesChange([...files, ...event.target.files]); event.target.value = ""; }} />
        <IconButton icon="attach" label={t("attach")} disabled={sending || chatAvailable !== true || voiceState !== "idle"} onClick={() => fileInput.current.click()} />
        {voiceAvailable && <IconButton
          icon={voiceState === "idle" ? "mic" : voiceState === "connecting" ? "close" : "stop"}
          label={t(voiceLabel)} aria-pressed={voiceState !== "idle"}
          disabled={voiceState === "stopping" || (voiceState === "idle" && (busy || sending || files.length > 0 || !connected))}
          onClick={onToggleVoice}
        />}
        {busy && <IconButton icon="stop" label={t("stop")} onClick={onInterrupt} />}
        <IconButton icon="send" label={t("send")} type="submit" className="primary" disabled={!canSubmit} />
      </div>
    </form>
  </div>;
}
