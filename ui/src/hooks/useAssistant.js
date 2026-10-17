import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { api as defaultApi } from "../api";
import { RemoteRealtimeTranscriptAssembler } from "../realtime-transcript";
import { voiceSession } from "../voice";
import { translate } from "../locales.js";
import { contextState, initialContext } from "../context.js";
import { pluginRunning } from "../plugins";
import { conversationBusy, conversationCommand, eventMessages, providerArtifacts, snapshot, voiceCaptions } from "../session";

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
  const [voiceState, setVoiceState] = useState("idle");
  const [chatAvailable, setChatAvailable] = useState(null);
  const [voiceAvailable, setVoiceAvailable] = useState(false);
  const [captions, setCaptions] = useState({});
  const voice = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    api("plugins", { signal: controller.signal })
      .then((result) => {
        setChatAvailable(pluginRunning(result.plugins, "chat"));
        setVoiceAvailable(pluginRunning(result.plugins, "realtime"));
      })
      .catch((cause) => {
        if (cause.name !== "AbortError") setError(cause.message);
      });
    return () => controller.abort();
  }, [api, refreshKey]);
  useEffect(() => {
    if (!voiceAvailable) return undefined;
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
    );
    voice.current = session;
    return () => {
      mounted = false;
      void session.stop();
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
  const followLatest = useCallback(() => {
    if (follow.current) scroll.current?.scrollTo({ top: scroll.current.scrollHeight });
  }, []);
  const onScroll = useCallback(() => {
    const element = scroll.current;
    follow.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
  }, []);
  useEffect(() => {
    let disposed = false,
      socket,
      retry,
      voiceCallId,
      attempts = 0,
      revision = 0,
      statusLoading = false,
      workerError = null;
    const controller = new AbortController();
    const transcripts = new RemoteRealtimeTranscriptAssembler();
    function workerRecovered() {
      if (workerError === null) return;
      const recovered = workerError;
      workerError = null;
      setError((current) => current === recovered ? "" : current);
    }
    function updateContext(output) {
      contextRevision.current++;
      setContext((current) => contextState(current, output));
    }
    async function refreshStatus() {
      if (disposed || statusLoading) return;
      statusLoading = true;
      const requested = contextRevision.current;
      try {
        const status = await api("status", { signal: controller.signal });
        if (!disposed && requested === contextRevision.current) {
          workerRecovered();
          setContext((current) => contextState(current, status));
          setBusy(conversationBusy(status));
        }
      } finally { statusLoading = false; }
    }
    async function reconcile() {
      const requested = ++revision;
      const requestedContext = contextRevision.current;
      const [page, status] = await Promise.all([
        api("session", { signal: controller.signal }),
        api("status", { signal: controller.signal }),
      ]);
      if (!disposed && requested === revision) {
        setMessages((items) => snapshot(items, page));
        if (!historyInitialized.current) {
          setBefore(page.has_more ? page.next_before : null);
          historyInitialized.current = true;
        }
        if (requestedContext === contextRevision.current) {
          workerRecovered();
          setBusy(conversationBusy(status));
          setContext((current) => contextState(current, status));
        }
      }
    }
    function connect() {
      const active = new WebSocket(
        eventsUrl, eventProtocol,
      );
      socket = active;
      const current = () => !disposed && socket === active;
      active.onopen = () => {
        if (!current()) return;
        attempts = 0;
        setConnection("Connected");
        reconcile().catch(fail);
      };
      active.onmessage = ({ data }) => {
        if (!current()) return;
        const output = JSON.parse(data);
        if (["worker_status", "command_accepted", "command_completed", "command_failed", "worker_exited", "worker_transport_error"].includes(output.type) ||
            (output.type === "command_event" && ["agent.compaction.start", "agent.compaction.end", "agent.generation.start", "agent.turn.start"].includes(output.event?.type)))
          updateContext(output);
        if (output.type === "command_event" && output.event?.type === "agent.compaction.end")
          refreshStatus().catch(fail);
        if (output.type === "command_failed" && output.error) setError(output.error);
        if (["worker_exited", "worker_transport_error"].includes(output.type)) {
          setArtifacts([]);
          workerError = output.error || translate("workerDisconnected");
          setError(workerError);
        }
        if (output.type === "realtime_event" && output.call_id !== voiceCallId) {
          voiceCallId = output.call_id;
          transcripts.reset();
          setCaptions({});
        }
        const transcript = transcripts.ingest(output);
        if (transcript) setCaptions((current) => voiceCaptions(current, transcript));
        if (output.type === "interface_refresh_requested") {
          location.reload();
          return;
        }
        if (output.type === "command_event") {
          const event = output.event;
          setArtifacts((items) => providerArtifacts(items, event));
          setMessages((items) => eventMessages(items, event));
          if (event.user_feedback) setActivity(event.user_feedback);
        }
        if (output.type === "worker_status") {
          workerRecovered();
          setBusy(conversationBusy(output));
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
        setArtifacts([]);
        void voice.current?.stop();
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
      if (!disposed && error.name !== "AbortError") setError(error.message);
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
      socket?.close();
    };
  }, [api, eventsUrl, eventProtocol]);
  useEffect(() => {
    followLatest();
  }, [messages, artifacts, activity, captions, followLatest]);
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
    if (chatAvailable !== true || sending || connection !== "Connected" || (!text.trim() && !files.length)) return false;
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
    context, compact,
    messages, artifacts, captions, before, loadingHistory, loadHistory, scroll, follow, onScroll, onContentLoad: followLatest,
    sending, connection, activity, busy,
    error, setError, chatAvailable, voiceAvailable, voiceState, send,
    toggleVoice: () => voiceState === "idle" ? voice.current.start() : voice.current.stop(),
    interrupt: () => api("agent/interrupt", { method: "POST", body: {} }).catch((error) => setError(error.message)),
  };
}
