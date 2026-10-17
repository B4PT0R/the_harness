import React, { useLayoutEffect, useRef, useState } from "react";
import { useLocale } from "../i18n";
import { initialContext } from "../context.js";
import { ContextGauge } from "./ContextGauge";
import { IconButton } from "./Icons";
import { handleComposerKeyDown } from "../composer-keyboard.js";
import { resizeComposerTextarea } from "../composer-size.js";

export function Composer({ readOnly = false, sending, chatAvailable, voiceAvailable, voiceState, busy, connected, context = initialContext, onCompact, activity, error, onDismissError, onSubmit, onToggleVoice, onInterrupt }) {
  const { t } = useLocale();
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState([]);
  const submitting = useRef(false);
  const fileInput = useRef(null);
  const textarea = useRef(null);
  useLayoutEffect(() => { resizeComposerTextarea(textarea.current); }, [draft]);
  useLayoutEffect(() => {
    const element = textarea.current;
    let width = element.getBoundingClientRect().width;
    const observer = new ResizeObserver(() => {
      const nextWidth = element.getBoundingClientRect().width;
      if (nextWidth !== width) {
        width = nextWidth;
        resizeComposerTextarea(element);
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const canSubmit = !readOnly && !sending && chatAvailable === true && (Boolean(draft.trim()) || files.length > 0) && connected;
  async function submit(event) {
    event.preventDefault();
    if (!canSubmit || submitting.current) return;
    submitting.current = true;
    try {
      if (await onSubmit({ text: draft, files })) {
        setDraft("");
        setFiles([]);
      }
    } finally { submitting.current = false; }
  }
  const activityLabel = {
    queued: "compactionQueued", running: "compacting", done: "compactionDone", failed: "compactionFailed",
  }[context.phase];
  const activityText = activityLabel ? t(activityLabel)
    : chatAvailable === false ? t("chatUnavailable") : busy ? activity || t("working") : "";
  const voiceLabel = voiceState === "idle" ? "voiceStart" : voiceState === "connecting" ? "cancel" : voiceState === "stopping" ? "voiceStopping" : "voiceEnd";
  return <div className="composer-area">
    {error && <div className="error" role="alert">{error}<IconButton icon="close" label={t("close")} onClick={onDismissError} /></div>}
    <div className="activity" role="status">{activityText}</div>
    <form className="composer" onSubmit={submit}>
      {!!files.length && <div className="attachments">{files.map((file, index) => <button
        type="button" key={index} disabled={sending} aria-label={t("removeAttachment", { name: file.name })}
        onClick={() => setFiles(files.filter((_, i) => i !== index))}
      >{file.name} ×</button>)}</div>}
      <label className="sr-only" htmlFor="message">{t("message")}</label>
      <textarea ref={textarea} id="message" placeholder={t("messagePlaceholder")} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => handleComposerKeyDown(event, canSubmit)} rows={1} disabled={sending || chatAvailable !== true} />
      <div className="composer-actions">
        <input ref={fileInput} type="file" multiple hidden onChange={(event) => { setFiles([...files, ...event.target.files]); event.target.value = ""; }} />
        <IconButton icon="attach" label={t("attach")} disabled={sending || chatAvailable !== true || voiceState !== "idle"} onClick={() => fileInput.current.click()} />
        <div className="composer-main-actions">
          <ContextGauge context={context} disabled={readOnly || !connected || sending || voiceState !== "idle"} onCompact={onCompact} />
          {voiceAvailable && <IconButton
            icon={voiceState === "idle" ? "mic" : voiceState === "connecting" ? "close" : "stop"}
            label={t(voiceLabel)} aria-pressed={voiceState !== "idle"}
            disabled={readOnly || voiceState === "stopping" || (voiceState === "idle" && (busy || sending || files.length > 0 || !connected))}
            onClick={onToggleVoice}
          />}
          {busy && <IconButton icon="stop" label={t("stop")} disabled={readOnly} onClick={onInterrupt} />}
          <IconButton icon="send" label={t("send")} type="submit" className="primary composer-send" disabled={!canSubmit} />
        </div>
      </div>
    </form>
  </div>;
}
