import React, { memo } from "react";
import { useLocale } from "../i18n";
import { IconButton } from "./Icons";
import { Markdown } from "./Markdown";
import { Artifact } from "./Artifact";
import { conversationBlocks } from "../session";

const Message = memo(function Message({ role, text, kind, live = false }) {
  const { t } = useLocale();
  const voice = role === "assistant" && kind === "realtime";
  return <article className={`message ${role}`} aria-label={t(role === "user" ? "you" : "assistant")}>
    {(voice || live) && <small className="message-source">
      {voice && t("voiceAgent")}{voice && live && " · "}{live && t("live")}
    </small>}
    <Markdown>{text}</Markdown>
  </article>;
});
// Draft edits must not parse and render the conversation's Markdown again.
export const Conversation = memo(function Conversation({ messages, artifacts = [], captions, subagents = {}, before, loadingHistory, onLoadHistory, scrollRef, onScroll, onContentLoad, artifactRenderers }) {
  const { t } = useLocale();
  return <section className="conversation" ref={scrollRef} aria-label={t("conversation")} onScroll={onScroll} onLoadCapture={onContentLoad}>
    {before && <IconButton icon="history" label={t(loadingHistory ? "loading" : "previousMessages")} onClick={onLoadHistory} disabled={loadingHistory} />}
    {conversationBlocks(messages).map((message) => message.type === "delegation"
      ? <details key={message.id} className="message text-agent-output">
        <summary>{t("textAgent")}</summary>
        <div className="text-agent-content">
          {message.messages.map((item) => <Message key={item.id} {...item} />)}
        </div>
      </details>
      : message.type === "artifact"
      ? <Artifact key={message.id} {...message} renderers={artifactRenderers} />
      : <Message key={message.id} {...message} />)}
    {artifacts.map((item) => <Artifact key={`provider-${item.id}`} {...item} temporary renderers={artifactRenderers} />)}
    {Object.entries(subagents).map(([task, value]) => <aside key={task} className="message subagent-activity" role="status">
      <small className="message-live">{t("subagent")} · {value.agent}</small>
      <p>{value.feedback || t("subagentWorking")}</p>
    </aside>)}
    {Object.entries(captions).map(([role, text]) => <Message key={role} role={role} kind="realtime" text={text} live />)}
  </section>;
});
