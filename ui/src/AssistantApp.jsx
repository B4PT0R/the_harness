import React, { useState } from "react";
import { api } from "./api";
import { LocaleProvider } from "./i18n";
import { useAssistant } from "./hooks/useAssistant";
import { AppShell } from "./components/AppShell";
import { Conversation } from "./components/Conversation";
import { Composer } from "./components/Composer";
import { Settings } from "./components/Settings";
import { ResourceRequest } from "./components/ResourceLink";
import "./theme.css";
import "./style.css";

const preview = document.querySelector('meta[name="framework-client-role"]')?.content === 'preview';

function Assistant({ request = api, eventsUrl, eventProtocol, brandIcon = "./assistant.svg", artifactRenderers }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const state = useAssistant({ request, eventsUrl, eventProtocol, refreshKey: settingsOpen });
  return <ResourceRequest.Provider value={request}><AppShell preview={preview} connection={state.connection} settingsOpen={settingsOpen} onToggleSettings={() => setSettingsOpen((value) => !value)} brandIcon={brandIcon}
    settings={settingsOpen && <Settings readOnly={preview} api={request} onClose={() => setSettingsOpen(false)} />}
  >
    <Conversation messages={state.messages} artifacts={state.artifacts} captions={state.captions} before={state.before} loadingHistory={state.loadingHistory} onLoadHistory={state.loadHistory} scrollRef={state.scroll}
      onScroll={state.onScroll} onContentLoad={state.onContentLoad} artifactRenderers={artifactRenderers}
    />
    <Composer readOnly={preview} sending={state.sending}
      chatAvailable={state.chatAvailable} voiceAvailable={state.voiceAvailable} voiceState={state.voiceState} busy={state.busy} connected={state.connection === "Connected"}
      context={state.context} onCompact={state.compact}
      activity={state.activity} error={state.error} onDismissError={() => state.setError("")} onSubmit={state.send} onToggleVoice={state.toggleVoice} onInterrupt={state.interrupt}
    />
  </AppShell></ResourceRequest.Provider>;
}
export function AssistantApp(props) {
  return <LocaleProvider><Assistant {...props} /></LocaleProvider>;
}
