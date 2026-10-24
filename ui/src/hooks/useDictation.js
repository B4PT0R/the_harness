import { useEffect, useRef, useState } from "react";
import { createDictation, dictationPCM, dictationSupported } from "../dictation.js";
import { translate } from "../locales.js";

export function useDictation({ request, locale, enabled, onText }) {
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");
  const session = useRef(null);
  const receive = useRef(onText);
  receive.current = onText;
  useEffect(() => {
    const current = createDictation({
      onState: setState,
      onText: text => receive.current(text),
      onError: cause => setError(translate(
        cause.name === "NotAllowedError" ? "dictationPermission"
          : ["dictationEmpty", "dictationTooLarge"].includes(cause.message) ? cause.message : "dictationFailed",
        {}, locale)),
      transcribe: async (audio, signal) => {
        const body = new FormData();
        body.append("files", await dictationPCM(audio, signal), "dictation.pcm");
        body.append("language", locale);
        const result = await request("dictation/transcribe", { method: "POST", body, signal });
        return result.text;
      },
    });
    session.current = current;
    setState("idle");
    return () => { current.dispose(); session.current = null; };
  }, [request, locale]);
  useEffect(() => { if (!enabled) session.current?.cancel(); }, [enabled]);
  function toggle() {
    setError("");
    if (state === "recording") session.current?.stop();
    else if (state !== "idle") session.current?.cancel();
    else if (enabled) void session.current?.start();
  }
  return { state, error, dismissError: () => setError(""), toggle, supported: dictationSupported() };
}
