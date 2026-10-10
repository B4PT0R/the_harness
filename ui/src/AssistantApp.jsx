import React, { useState } from "react";
import { api } from "./api";
import { LocaleProvider } from "./i18n";
import { useAssistant } from "./hooks/useAssistant";
import { AppShell } from "./components/AppShell";
import { Conversation } from "./components/Conversation";
import { Composer } from "./components/Composer";
import { Settings } from "./components/Settings";
import "./theme.css";
import "./style.css";

function Assistant({ request = api, eventsUrl, eventProtocol, brandIcon = "./assistant.svg" }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const state = useAssistant({ request, eventsUrl, eventProtocol, refreshKey: settingsOpen });
  return <AppShell connection={state.connection} settingsOpen={settingsOpen} onToggleSettings={() => setSettingsOpen((value) => !value)} brandIcon={brandIcon}
    settings={settingsOpen && <Settings api={request} onClose={() => setSettingsOpen(false)} report={state.setError} />}
  >
    <Conversation messages={state.messages} captions={state.captions} before={state.before} loadingHistory={state.loadingHistory} onLoadHistory={state.loadHistory} scrollRef={state.scroll}
      onScroll={() => { const el = state.scroll.current; state.follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}
    />
    <Composer draft={state.draft} onDraftChange={state.setDraft} files={state.files} onFilesChange={state.setFiles} sending={state.sending}
      chatAvailable={state.chatAvailable} voiceAvailable={state.voiceAvailable} voiceState={state.voiceState} busy={state.busy} connected={state.connection === "Connected"}
      context={state.context} onCompact={state.compact}
      activity={state.activity} error={state.error} onDismissError={() => state.setError("")} onSubmit={state.send} onToggleVoice={state.toggleVoice} onInterrupt={state.interrupt}
    />
  </AppShell>;
}
export function AssistantApp(props) {
  return <LocaleProvider><Assistant {...props} /></LocaleProvider>;
}
