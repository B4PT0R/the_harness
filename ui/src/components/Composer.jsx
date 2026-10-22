import React, { useLayoutEffect, useRef, useState } from "react";
import { useLocale } from "../i18n";
import { initialContext } from "../context.js";
import { QuotaGauge } from "./QuotaGauge";
import { ContextGauge } from "./ContextGauge";
import { IconButton } from "./Icons";
import { handleComposerKeyDown } from "../composer-keyboard.js";
import { resizeComposerTextarea } from "../composer-size.js";

export function Composer({ quota, server = { phase: "idle" }, onDismissServer, readOnly = false, sending, voiceAvailable, voiceState, busy, connected, context = initialContext, onCompact, activity, error, onDismissError, onSubmit, onToggleVoice, onInterrupt }) {
  const { t } = useLocale();
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState([]);
  const [restoreFocus, setRestoreFocus] = useState(false);
  const submitting = useRef(false);
  const fileInput = useRef(null);
  const textarea = useRef(null);
  useLayoutEffect(() => { resizeComposerTextarea(textarea.current); }, [draft]);
  useLayoutEffect(() => {
    if (sending || !restoreFocus) return;
    setRestoreFocus(false);
    const element = textarea.current;
    // Wait for re-enabling, without stealing focus from settings or another control.
    if (element.getClientRects().length && (document.activeElement === document.body
        || element.form.contains(document.activeElement))) {
      element.focus({ preventScroll: true });
    }
  }, [sending, restoreFocus]);
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
  const canSubmit = !readOnly && !sending && (Boolean(draft.trim()) || files.length > 0) && connected;
  async function submit(event) {
    event.preventDefault();
    if (!canSubmit || submitting.current) return;
    submitting.current = true;
    try {
      if (await onSubmit({ text: draft, files })) {
        setDraft("");
        setFiles([]);
      }
    } finally {
      submitting.current = false;
      setRestoreFocus(true);
    }
  }
  const activityLabel = {
    queued: "compactionQueued", running: "compacting", done: "compactionDone", failed: "compactionFailed",
  }[context.phase];
  const activityText = activityLabel ? t(activityLabel)
    : busy ? activity || t("working") : "";
  const voiceLabel = voiceState === "idle" ? "voiceStart" : voiceState === "connecting" ? "cancel" : voiceState === "stopping" ? "voiceStopping" : "voiceEnd";
  return <div className="composer-area">
    {server.phase !== "idle" && <div className="server-notice" data-phase={server.phase} role={server.phase === "failed" ? "alert" : "status"}>
      <span>{t({ restarting: "serverRestarting", waiting: "serverRestartWaiting", restarted: "serverRestarted", failed: "serverRestartFailed" }[server.phase])}
        {server.phase === "failed" && server.error && <small>{server.error}</small>}
      </span>
      {["restarted", "failed"].includes(server.phase) && <IconButton icon="close" label={t("close")} onClick={onDismissServer} />}
    </div>}
    {error && <div className="error" role="alert">{error}<IconButton icon="close" label={t("close")} onClick={onDismissError} /></div>}
    <div className="activity" role="status" aria-live="polite" aria-atomic="true">
      {activityText && <div className="activity-card" data-active={busy || ["queued", "running"].includes(context.phase)}>
        <span className="activity-indicator" aria-hidden="true" />
        <span className="activity-text">{activityText}</span>
      </div>}
    </div>
    <form className="composer" onSubmit={submit}>
      {!!files.length && <div className="attachments">{files.map((file, index) => <button
        type="button" key={index} disabled={sending} aria-label={t("removeAttachment", { name: file.name })}
        onClick={() => setFiles(files.filter((_, i) => i !== index))}
      >{file.name} ×</button>)}</div>}
      <label className="sr-only" htmlFor="message">{t("message")}</label>
      <textarea ref={textarea} id="message" placeholder={t("messagePlaceholder")} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => handleComposerKeyDown(event, canSubmit)} rows={1} disabled={sending} />
      <div className="composer-actions">
        <input ref={fileInput} type="file" multiple hidden onChange={(event) => { setFiles([...files, ...event.target.files]); event.target.value = ""; }} />
        <IconButton icon="attach" label={t("attach")} disabled={sending || voiceState !== "idle"} onClick={() => fileInput.current.click()} />
        <div className="composer-main-actions">
          {quota && <QuotaGauge quota={quota} readOnly={readOnly} />}
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
