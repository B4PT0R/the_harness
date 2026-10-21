import React, { useState } from "react";
import { api } from "./api";
import { LocaleProvider } from "./i18n";
import { restartPending } from "./server-lifecycle.js";
import { useAssistant } from "./hooks/useAssistant";
import { AppShell } from "./components/AppShell";
import { Conversation } from "./components/Conversation";
import { Composer } from "./components/Composer";
import { Settings } from "./components/Settings";
import { MobileSettings } from "./components/DeviceSettings";
import { ResourceRequest } from "./components/ResourceLink";
import "./theme.css";
import "./style.css";

const mobile = location.hostname.endsWith(".ts.net");
const preview = document.querySelector('meta[name="framework-client-role"]')?.content === 'preview';

function Assistant({ request = api, eventsUrl, eventProtocol, brandIcon = "./assistant.svg", artifactRenderers }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const state = useAssistant({ request, eventsUrl: eventsUrl || (mobile ? `wss://${location.host}/remote/v1/ui-events` : undefined), eventProtocol, refreshKey: settingsOpen });
  return <ResourceRequest.Provider value={request}><AppShell preview={preview} connection={state.connection} settingsOpen={settingsOpen} onToggleSettings={() => setSettingsOpen((value) => !value)} brandIcon={brandIcon}
    settings={settingsOpen && (mobile ? <MobileSettings onClose={() => setSettingsOpen(false)} /> : <Settings readOnly={preview} api={request} onClose={() => setSettingsOpen(false)} />)}
  >
    <Conversation messages={state.messages} artifacts={state.artifacts} captions={state.captions} subagents={state.subagents} before={state.before} loadingHistory={state.loadingHistory} onLoadHistory={state.loadHistory} scrollRef={state.scroll}
      onScroll={state.onScroll} onContentLoad={state.onContentLoad} artifactRenderers={artifactRenderers}
    />
    <Composer server={state.server} onDismissServer={state.dismissServer} readOnly={preview} sending={state.sending}
      voiceAvailable={state.voiceAvailable} voiceState={state.voiceState} busy={state.busy} connected={state.connection === "Connected" && !restartPending(state.server)}
      context={state.context} onCompact={state.compact}
      activity={state.activity} error={state.error} onDismissError={() => state.setError("")} onSubmit={state.send} onToggleVoice={state.toggleVoice} onInterrupt={state.interrupt}
    />
  </AppShell></ResourceRequest.Provider>;
}
export function AssistantApp(props) {
  return <LocaleProvider><Assistant {...props} /></LocaleProvider>;
}
