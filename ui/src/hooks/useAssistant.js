import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api as defaultApi } from "../api";
import { RemoteRealtimeTranscriptAssembler } from "../realtime-transcript";
import { voiceSession } from "../voice";
import { pluginRunning } from "../plugins";
import { conversationBusy, conversationCommand, eventMessages, snapshot, voiceCaptions } from "../session";

// Browser client state only. Conversation history remains owned by the server.
// Hosts can supply their request function and event endpoint without changing UI.
export function useAssistant({ request = defaultApi, eventsUrl = `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/v1/events`, eventProtocol = "the-harness", refreshKey } = {}) {
  const api = request;
  const [messages, setMessages] = useState([]);
  const [before, setBefore] = useState(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const historyInitialized = useRef(false);
  const historyScroll = useRef(null);
  const [draft, setDraft] = useState("");
  const [files, setFiles] = useState([]);
  const [sending, setSending] = useState(false);
  const [connection, setConnection] = useState("Connecting");
  const [activity, setActivity] = useState("");
  const [busy, setBusy] = useState(false);
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
  const scroll = useRef(null);
  const follow = useRef(true);
  useEffect(() => {
    let disposed = false,
      socket,
      retry,
      voiceCallId,
      attempts = 0,
      revision = 0;
    const controller = new AbortController();
    const transcripts = new RemoteRealtimeTranscriptAssembler();
    async function reconcile() {
      const requested = ++revision;
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
        setBusy(conversationBusy(status));
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
          setMessages((items) => eventMessages(items, event));
          if (event.user_feedback) setActivity(event.user_feedback);
        }
        if (output.type === "worker_status") setBusy(conversationBusy(output));
        if (output.type === "command_accepted" && conversationCommand(output))
          setBusy(true);
        if (
          ["command_completed", "command_failed"].includes(output.type) &&
          conversationCommand(output)
        ) {
          if (output.error) setError(output.error);
          setActivity("");
          reconcile().catch(fail);
        }
      };
      active.onclose = () => {
        if (!current()) return;
        void voice.current?.stop();
        transcripts.reset();
        setCaptions({});
        revision++;
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
    return () => {
      disposed = true;
      controller.abort();
      clearTimeout(retry);
      socket?.close();
    };
  }, [api, eventsUrl, eventProtocol]);
  useEffect(() => {
    if (follow.current)
      scroll.current?.scrollTo({ top: scroll.current.scrollHeight });
  }, [messages, activity, captions]);
  useLayoutEffect(() => {
    if (historyScroll.current && scroll.current) {
      const { height, top } = historyScroll.current;
      scroll.current.scrollTop = top + scroll.current.scrollHeight - height;
      historyScroll.current = null;
    }
  }, [messages]);
  async function loadHistory() {
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
  }
  async function send(event) {
    event.preventDefault();
    if (chatAvailable !== true || sending || (!draft.trim() && !files.length)) return;
    const text = draft;
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
      setDraft("");
      setFiles([]);
      follow.current = true;
    } catch (error) {
      setError(error.message);
      setBusy(false);
    } finally {
      setSending(false);
    }
  }
  return {
    messages, captions, before, loadingHistory, loadHistory, scroll, follow,
    draft, setDraft, files, setFiles, sending, connection, activity, busy,
    error, setError, chatAvailable, voiceAvailable, voiceState, send,
    toggleVoice: () => voiceState === "idle" ? voice.current.start() : voice.current.stop(),
    interrupt: () => api("agent/interrupt", { method: "POST", body: {} }).catch((error) => setError(error.message)),
  };
}
