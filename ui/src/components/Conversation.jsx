import React, { memo } from "react";
import { useLocale } from "../i18n";
import { IconButton } from "./Icons";
import { Markdown } from "./Markdown";
import { Artifact } from "./Artifact";

const Message = memo(function Message({ role, text, live = false }) {
  const { t } = useLocale();
  return <article className={`message ${role}`} aria-label={t(role === "user" ? "you" : "assistant")}>
    {live && <small className="message-live">{t("live")}</small>}
    <Markdown>{text}</Markdown>
  </article>;
});
// Draft edits must not parse and render the conversation's Markdown again.
export const Conversation = memo(function Conversation({ messages, artifacts = [], captions, before, loadingHistory, onLoadHistory, scrollRef, onScroll, onContentLoad, artifactRenderers }) {
  const { t } = useLocale();
  return <section className="conversation" ref={scrollRef} aria-label={t("conversation")} onScroll={onScroll} onLoadCapture={onContentLoad}>
    {before && <IconButton icon="history" label={t(loadingHistory ? "loading" : "previousMessages")} onClick={onLoadHistory} disabled={loadingHistory} />}
    {messages.map((message) => message.type === "artifact"
      ? <Artifact key={message.id} {...message} renderers={artifactRenderers} />
      : <Message key={message.id} {...message} />)}
    {artifacts.map((item) => <Artifact key={`provider-${item.id}`} {...item} temporary renderers={artifactRenderers} />)}
    {Object.entries(captions).map(([role, text]) => <Message key={role} role={role} text={text} live />)}
  </section>;
});
