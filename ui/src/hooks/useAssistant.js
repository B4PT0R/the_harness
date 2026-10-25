import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { clientEventsUrl, clientOutput } from "../client-output.js";
import { api as defaultApi } from "../api";
import { RemoteRealtimeTranscriptAssembler } from "../realtime-transcript";
import { voiceSession } from "../voice";
import { translate } from "../locales.js";
import { contextState, initialContext } from "../context.js";
import { initialServer, restartPending, restoreServer, serverLifecycle } from "../server-lifecycle.js";
import { pluginBindingEnabled } from "../plugins";
import { conversationBusy, conversationCommand, eventMessages, providerArtifacts, snapshot, voiceCaptions, voiceMessages, subagentActivities } from "../session";

// Browser client state only. Conversation history remains owned by the server.
// Hosts can supply their request function and event endpoint without changing UI.
export function useAssistant({ request = defaultApi, eventsUrl = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/v1/events`, eventProtocol = "the-harness", refreshKey } = {}) {
  const api = request;
  const [messages, setMessages] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [before, setBefore] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const historyInitialized = useRef(false);
  const historyScroll = useRef(null);
  const [sending, setSending] = useState(false);
  const [connection, setConnection] = useState("Connecting");
  const [activity, setActivity] = useState("");
  const [busy, setBusy] = useState(false);
  const [context, setContext] = useState(initialContext);
  const compactSubmitting = useRef(false);
  const contextRevision = useRef(0);
  const [error, setError] = useState("");
  const restartKey = `server-restart:${eventsUrl}`;
  const [server, setServer] = useState(() => restoreServer(window.sessionStorage, restartKey));
  const serverRef = useRef(server);
  const updateServer = useCallback((output) => {
    const next = serverLifecycle(serverRef.current, output);
    serverRef.current = next;
    setServer(next);
    try {
      if (restartPending(next)) window.sessionStorage.setItem(restartKey, JSON.stringify(next));
      else window.sessionStorage.removeItem(restartKey);
    } catch { /* Storage may be disabled. */ }
  }, [restartKey]);
  useEffect(() => {
    if (!["restarting", "restarted"].includes(server.phase)) return;
    const timer = setTimeout(() => {
      const current = serverRef.current;
      if (current.phase !== server.phase || current.instanceId !== server.instanceId) return;
      const next = { ...current, phase: server.phase === "restarted" ? "idle" : "waiting" };
      serverRef.current = next;
      setServer(next);
    }, server.phase === "restarted" ? 5000 : 30000);
    return () => clearTimeout(timer);
  }, [server.phase, server.instanceId]);
  const [voiceState, setVoiceState] = useState("idle");
  const [voiceAvailable, setVoiceAvailable] = useState(false);
  const [dictationAvailable, setDictationAvailable] = useState(false);
  const [captions, setCaptions] = useState({});
  const [subagents, setSubagents] = useState({});
  const voice = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    api("plugins", { signal: controller.signal })
      .then((result) => {
        setVoiceAvailable(pluginBindingEnabled(result.plugins, "realtime"));
        setDictationAvailable(result.plugins.some(plugin => plugin.name === "dictation" && plugin.running));
      })
      .catch((cause) => {
        if (cause.name !== "AbortError") setError(cause.message);
      });
    return () => controller.abort();
  }, [api, refreshKey]);
  useEffect(() => {
    if (!voiceAvailable || document.querySelector('meta[name="framework-client-role"]')?.content === "preview") return undefined;
    let mounted = true;
    const session = voiceSession(
      api,
      new Audio(),
      (state) => {
        if (mounted) {
          setVoiceState(state);
          if (state === "idle") setCaptions({});
        }
      },
      (message) => {
        if (mounted) setError(message);
      },
      undefined,
      { storage: window.sessionStorage, storageKey: `voice:${eventsUrl}` },
    );
    voice.current = session;
    if (connection === "Connected") {
      api("status").then(status => {
        if (mounted && !restartPending(serverRef.current) && !conversationBusy(status)) return session.resume();
      }).catch(cause => { if (mounted) setError(cause.message); });
    }
    return () => {
      mounted = false;
      void session.dispose();
      voice.current = null;
    };
  }, [api, voiceAvailable]);
  useEffect(() => {
    if (!["done", "failed"].includes(context.phase)) return;
    const timer = setTimeout(() => setContext((current) =>
      current.phase === context.phase ? { ...current, phase: "idle", commandId: null } : current
    ), 4000);
    return () => clearTimeout(timer);
  }, [context.phase]);
  const scroll = useRef(null);
  const follow = useRef(true);
  const lastScrollTop = useRef(0);
  const followLatest = useCallback(() => {
    const element = scroll.current;
    if (follow.current && element) {
      element.scrollTop = element.scrollHeight;
      lastScrollTop.current = element.scrollTop;
    }
  }, []);
  const onScroll = useCallback(() => {
    const element = scroll.current;
    // Content growth can deliver a scroll before the image load handler.
    // Leave follow mode only when the reader actually moves upward.
    if (element.scrollHeight - element.scrollTop - element.clientHeight < 80) follow.current = true;
    else if (element.scrollTop < lastScrollTop.current) follow.current = false;
    lastScrollTop.current = element.scrollTop;
  }, []);
  useEffect(() => {
    let disposed = false,
      socket,
      transportReady = false,
      retry,
      voiceCallId,
      attempts = 0,
      revision = 0,
      statusLoading = false,
      workerError = null,
      statusError = null;
    const controller = new AbortController();
    const transcripts = new RemoteRealtimeTranscriptAssembler();
    const media = clientOutput({
      send: (value) => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(value)); },
      onError: (message) => { if (!disposed) setError(message); },
    });
    function workerRecovered() {
      const recovered = [workerError, statusError];
      workerError = statusError = null;
      setError((current) => recovered.includes(current) ? "" : current);
    }
    function updateContext(output) {
      contextRevision.current++;
      setContext((current) => contextState(current, output));
    }
    async function readStatus() {
      try {
        return await api("status", { signal: controller.signal });
      } catch (cause) {
        if (!disposed && cause.name !== "AbortError") {
          statusError = cause.message;
          if (!restartPending(serverRef.current)) setError(statusError);
        }
        return null;
      }
    }
    async function refreshStatus() {
      if (disposed || statusLoading) return;
      statusLoading = true;
      const requested = contextRevision.current;
      try {
        const status = await readStatus();
        if (status && !disposed && requested === contextRevision.current) {
          updateServer(status);
          workerRecovered();
          setContext((current) => contextState(current, status));
          setBusy(conversationBusy(status));
          if (transportReady && !restartPending(serverRef.current) && !conversationBusy(status)) void voice.current?.resume();
        }
      } finally { statusLoading = false; }
    }
    async function reconcile() {
      const requested = ++revision;
      const requestedContext = contextRevision.current;
      const pageRequest = api("session", { signal: controller.signal }).then((page) => {
        if (disposed || requested !== revision) return;
        setMessages((items) => snapshot(items, page));
        if (!historyInitialized.current) {
          setBefore(page.has_more ? page.next_before : null);
          historyInitialized.current = true;
        }
      });
      const statusRequest = readStatus().then((status) => {
        if (!status || disposed || requested !== revision || requestedContext !== contextRevision.current) return;
        updateServer(status);
        workerRecovered();
        setBusy(conversationBusy(status));
        if (transportReady && !restartPending(serverRef.current) && !conversationBusy(status)) void voice.current?.resume();
        setContext((current) => contextState(current, status));
      });
      await Promise.all([pageRequest, statusRequest]);
    }

    function connect() {
      const active = new WebSocket(
        clientEventsUrl(eventsUrl), eventProtocol,
      );
      socket = active;
      const current = () => !disposed && socket === active;
      active.onopen = () => {
        if (!current()) return;
        attempts = 0;
        transportReady = true;
        setSubagents({});
        setConnection("Connected");
        reconcile().catch(fail);
      };
      active.onmessage = ({ data }) => {
        if (!current()) return;
        const output = JSON.parse(data);
        void media.handle(output).catch(fail);
        if (["server_restarting", "server_restart_failed"].includes(output.type)) {
          updateServer(output);
          // Voice has its own post-drain restarting event: do not cut speech here.
          transportReady = output.type !== "server_restarting";
          if (output.type === "server_restart_failed") refreshStatus().catch(fail);
        }
        if (output.type === "subagent_event") setSubagents((items) => subagentActivities(items, output));
        if (output.type === "realtime_control_requested") {
          void voice.current?.control(output);
        }
        if (output.type === "realtime_control_failed") setError(output.error);
        if (output.type === "realtime_restarting") {
          transportReady = false;
          void voice.current?.suspend(output);
        }
        if (output.type === "realtime_reconnect_requested") {
          void voice.current?.reconnect(output);
        }
        if (output.type === "command_event" && output.event?.type === "agent.plugin.binding.updated" && output.event.plugin === "realtime") {
          if (!output.event.enabled) void voice.current?.stop();
          setVoiceAvailable(Boolean(output.event.enabled));
        }
        if (["worker_status", "command_accepted", "command_completed", "command_failed", "worker_exited", "worker_transport_error"].includes(output.type) ||
            (output.type === "command_event" && ["agent.compaction.start", "agent.compaction.end", "agent.generation.start", "agent.turn.start"].includes(output.event?.type)))
          updateContext(output);
        if (output.type === "command_event" && ["agent.compaction.end", "agent.generation.end"].includes(output.event?.type))
          refreshStatus().catch(fail);
        if (output.type === "command_failed" && output.error &&
            !(restartPending(serverRef.current) && output.error === "interrupted")) setError(output.error);
        if (["worker_exited", "worker_transport_error"].includes(output.type)) {
          setArtifacts([]);
          setSubagents({});
          workerError = output.error || translate("workerDisconnected");
          if (!(restartPending(serverRef.current) && output.type === "worker_exited" && output.returncode === 0)) setError(workerError);
        }
        if (output.type === "realtime_event" && output.call_id !== voiceCallId) {
          voiceCallId = output.call_id;
          transcripts.reset();
          setCaptions({});
        }
        const transcript = transcripts.ingest(output);
        if (transcript) {
          setMessages((current) => voiceMessages(current, transcript));
          setCaptions((current) => voiceCaptions(current, transcript));
        }
        if (output.type === "interface_refresh_requested") {
          Promise.resolve(voice.current?.prepareReload()).then(() => location.reload()).catch(fail);
          return;
        }
        if (output.type === "subagent_event") setSubagents((items) => subagentActivities(items, output));
        if (output.type === "command_event") {
          const event = output.event;
          setArtifacts((items) => providerArtifacts(items, event));
          setMessages((items) => eventMessages(items, event));
          if (event.user_feedback) setActivity(event.user_feedback);
        }
        if (output.type === "worker_status") {
          workerRecovered();
          setBusy(conversationBusy(output));
          if (transportReady && !restartPending(serverRef.current) && !conversationBusy(output)) void voice.current?.resume();
        }
        if (output.type === "command_accepted" && conversationCommand(output))
          setBusy(true);
        if (
          ["command_completed", "command_failed"].includes(output.type) &&
          (conversationCommand(output) || output.command?.type === "compact_request")
        ) {
          if (conversationCommand(output)) setArtifacts([]);
          setActivity("");
          reconcile().catch(fail);
        }
      };
      active.onclose = () => {
        if (!current()) return;
        transportReady = false;
        media.stop();
        setArtifacts([]);
        void voice.current?.suspend();
        transcripts.reset();
        setCaptions({});
        revision++;
        contextRevision.current++;
        setConnection("Reconnecting");
        retry = setTimeout(
          connect,
          Math.min(10000, 500 * 2 ** attempts++) + Math.random() * 300,
        );
      };
      active.onerror = () => active.close();
    }
    function fail(error) {
      if (!disposed && error.name !== "AbortError" && !restartPending(serverRef.current)) setError(error.message);
    }
    connect();
    const statusTimer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN && document.visibilityState !== "hidden")
        refreshStatus().catch(fail);
    }, 5000);
    return () => {
      disposed = true;
      controller.abort();
      clearTimeout(retry);
      clearInterval(statusTimer);
      media.stop();
      socket?.close();
    };
  }, [api, eventsUrl, eventProtocol, updateServer]);
  useLayoutEffect(() => {
    followLatest();
  }, [messages, artifacts, activity, captions, subagents, followLatest]);
  useLayoutEffect(() => {
    if (historyScroll.current && scroll.current) {
      const { height, top } = historyScroll.current;
      scroll.current.scrollTop = top + scroll.current.scrollHeight - height;
      historyScroll.current = null;
    }
  }, [messages]);
  const loadHistory = useCallback(async () => {
    if (!before || loadingHistory) return;
    setLoadingHistory(true);
    try {
      const page = await api(`session?before=${encodeURIComponent(before)}`);
      follow.current = false;
      historyScroll.current = {
        height: scroll.current.scrollHeight,
        top: scroll.current.scrollTop,
      };
      setMessages((items) => snapshot(items, page));
      setBefore(page.has_more ? page.next_before : null);
    } catch (error) {
      setError(error.message);
    } finally {
      setLoadingHistory(false);
    }
  }, [api, before, loadingHistory]);
  // Return acceptance so the composer only clears its local draft after success.
  async function send({ text, files }) {
    if (sending || connection !== "Connected" || (!text.trim() && !files.length)) return false;
    setError("");
    if (voiceState === "idle") setBusy(true);
    setSending(true);
    try {
      const id = crypto.randomUUID();
      if (files.length) {
        const body = new FormData();
        body.append("id", id);
        body.append("prompt", text);
        files.forEach((file) => body.append("files", file));
        await api("agent/attachments", { method: "POST", body });
      } else {
        await api("agent/prompt", {
          method: "POST",
          body: { id, prompt: text },
        });
      }
      follow.current = true;
      return true;
    } catch (error) {
      setError(error.message);
      setBusy(false);
      return false;
    } finally {
      setSending(false);
    }
  }
  async function compact() {
    if (compactSubmitting.current || ["queued", "running"].includes(context.phase) || connection !== "Connected" || voiceState !== "idle") return;
    compactSubmitting.current = true;
    contextRevision.current++;
    setError("");
    setContext((current) => ({ ...current, phase: "queued", commandId: null }));
    try {
      await api("agent/compact", { method: "POST" });
    } catch (cause) {
      setError(cause.message);
      setContext((current) => ({ ...current, phase: "failed", commandId: null }));
    } finally { compactSubmitting.current = false; }
  }
  return {
    context, compact, server,
    dismissServer: () => { serverRef.current = { ...initialServer, instanceId: serverRef.current.instanceId }; setServer(serverRef.current); },
    messages, artifacts, captions, subagents, before, loadingHistory, loadHistory, scroll, follow, onScroll, onContentLoad: followLatest,
    sending, connection, activity, busy,
    error, setError, voiceAvailable, dictationAvailable, voiceState, send,
    toggleVoice: () => voiceState === "idle" ? voice.current.start() : voice.current.stop(),
    interrupt: () => api("agent/interrupt", { method: "POST", body: {} }).catch((error) => setError(error.message)),
  };
}
