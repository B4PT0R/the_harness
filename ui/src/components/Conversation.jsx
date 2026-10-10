import React, { memo } from "react";
import { useLocale } from "../i18n";
import { IconButton } from "./Icons";
import { Markdown } from "./Markdown";

const Message = memo(function Message({ role, text, live = false }) {
  const { t } = useLocale();
  return <article className={`message ${role}`} aria-label={t(role === "user" ? "you" : "assistant")}>
    {live && <small className="message-live">{t("live")}</small>}
    <Markdown>{text}</Markdown>
  </article>;
});
// Draft edits must not parse and render the conversation's Markdown again.
export const Conversation = memo(function Conversation({ messages, captions, before, loadingHistory, onLoadHistory, scrollRef, onScroll }) {
  const { t } = useLocale();
  return <section className="conversation" ref={scrollRef} aria-label={t("conversation")} onScroll={onScroll}>
    {before && <IconButton icon="history" label={t(loadingHistory ? "loading" : "previousMessages")} onClick={onLoadHistory} disabled={loadingHistory} />}
    {messages.map((message) => <Message key={message.id} {...message} />)}
    {Object.entries(captions).map(([role, text]) => <Message key={role} role={role} text={text} live />)}
  </section>;
});
